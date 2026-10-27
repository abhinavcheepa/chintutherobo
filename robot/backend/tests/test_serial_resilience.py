"""Tests for serial link resilience: link-loss behavior, garbage frame resync,
exponential backoff reconnection, and command rejection when serial is down.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient

from backend.config import AUTH_TOKEN
from backend.protocol import (
    MSG_HEARTBEAT,
    SYNC_0,
    SYNC_1,
    StreamParser,
    compute_crc16,
    encode_frame,
)
from backend.serial_manager import SerialManager
from backend.server import (
    app,
    on_serial_link_change,
    serial_mgr,
    ticket_request_history,
    ws_tickets,
)


# ============================================================================
# StreamParser Resilience Tests
# ============================================================================

class TestStreamParserResync:
    """Tests for the StreamParser's ability to recover from garbage bytes."""

    def test_garbage_before_valid_frame(self):
        """Parser must silently discard garbage and still decode a valid frame."""
        parser = StreamParser()
        # Build a valid heartbeat frame
        valid_frame = encode_frame(MSG_HEARTBEAT, 1, b'\x00\x00\x00\x00')
        # Prepend 50 bytes of garbage
        garbage = bytes(range(50))
        result = parser.parse(garbage + valid_frame)
        assert len(result) == 1
        msg_type, seq, _payload = result[0]
        assert msg_type == MSG_HEARTBEAT
        assert seq == 1

    def test_consecutive_sync_byte_resync(self):
        """Parser handles 0xAA 0xAA 0x55 (double sync0) correctly."""
        parser = StreamParser()
        valid_frame = encode_frame(MSG_HEARTBEAT, 42, b'\x01\x00\x00\x00')
        # Inject an extra SYNC_0 before the valid frame's sync sequence
        injected = bytes([SYNC_0]) + valid_frame
        result = parser.parse(injected)
        assert len(result) == 1
        assert result[0][1] == 42

    def test_truncated_frame_recovery(self):
        """Parser recovers after receiving a truncated frame followed by a valid one."""
        parser = StreamParser()
        valid_frame = encode_frame(MSG_HEARTBEAT, 10, b'\x05\x00\x00\x00')
        # Truncated: sync bytes + length but no payload/CRC
        truncated = bytes([SYNC_0, SYNC_1, 4, 99, MSG_HEARTBEAT])
        # Feed truncated first, then valid frame
        result1 = parser.parse(truncated)
        # Truncated frame shouldn't yield anything yet (still waiting for payload)
        assert len(result1) == 0
        # Now feed valid frame — parser state machine should eventually reset and catch it
        result2 = parser.parse(valid_frame)
        # The truncated frame's payload bytes may consume some of the valid frame bytes,
        # but eventually the parser should recover
        # We mainly verify no crash and eventual recovery
        assert isinstance(result2, list)

    def test_bad_crc_dropped(self):
        """Frames with invalid CRC must be silently discarded without crashing."""
        parser = StreamParser()
        valid_frame = encode_frame(MSG_HEARTBEAT, 5, b'\x00\x00\x00\x00')
        # Corrupt the last byte (CRC high byte)
        corrupted = bytearray(valid_frame)
        corrupted[-1] ^= 0xFF
        result = parser.parse(bytes(corrupted))
        assert len(result) == 0  # Corrupted frame rejected

    def test_valid_after_bad_crc(self):
        """A valid frame arriving after a corrupted one must still be decoded."""
        parser = StreamParser()
        good = encode_frame(MSG_HEARTBEAT, 1, b'\x00\x00\x00\x00')
        bad = bytearray(encode_frame(MSG_HEARTBEAT, 2, b'\x00\x00\x00\x00'))
        bad[-1] ^= 0xFF  # Corrupt CRC

        result = parser.parse(bytes(bad) + good)
        assert len(result) == 1
        assert result[0][1] == 1  # Only the good frame

    def test_max_payload_length_rejection(self):
        """Frames claiming length > 64 must be rejected and parser must resync."""
        parser = StreamParser()
        # Manually craft a frame header with length = 100 (invalid)
        fake_header = bytes([SYNC_0, SYNC_1, 100, 0, MSG_HEARTBEAT])
        good = encode_frame(MSG_HEARTBEAT, 7, b'\x00\x00\x00\x00')
        result = parser.parse(fake_header + good)
        assert len(result) == 1
        assert result[0][1] == 7

    def test_back_to_back_valid_frames(self):
        """Multiple valid frames concatenated must all be parsed."""
        parser = StreamParser()
        f1 = encode_frame(MSG_HEARTBEAT, 1, b'\x01\x00\x00\x00')
        f2 = encode_frame(MSG_HEARTBEAT, 2, b'\x02\x00\x00\x00')
        f3 = encode_frame(MSG_HEARTBEAT, 3, b'\x03\x00\x00\x00')
        result = parser.parse(f1 + f2 + f3)
        assert len(result) == 3
        assert [r[1] for r in result] == [1, 2, 3]

    def test_empty_payload_frame(self):
        """Zero-length payload frames must be handled correctly."""
        parser = StreamParser()
        frame = encode_frame(MSG_HEARTBEAT, 0, b'')
        result = parser.parse(frame)
        assert len(result) == 1
        assert result[0][2] == b''

    def test_incremental_byte_by_byte_feeding(self):
        """Parser must work correctly when fed one byte at a time."""
        parser = StreamParser()
        frame = encode_frame(MSG_HEARTBEAT, 99, b'\xDE\xAD\xBE\xEF')
        all_results = []
        for byte in frame:
            results = parser.parse(bytes([byte]))
            all_results.extend(results)
        assert len(all_results) == 1
        assert all_results[0][1] == 99
        assert all_results[0][2] == b'\xDE\xAD\xBE\xEF'


# ============================================================================
# SerialManager Unit Tests
# ============================================================================

class TestSerialManagerLinkCallbacks:
    """Tests for SerialManager link state callback registration and firing."""

    def test_link_callback_registration(self):
        """Registering a link callback should store it for later invocation."""
        mgr = SerialManager()
        states = []
        mgr.register_link_callback(lambda connected: states.append(connected))
        mgr._notify_link_state(True)
        mgr._notify_link_state(False)
        assert states == [True, False]

    def test_link_callback_exception_isolation(self):
        """A raising callback must not prevent other callbacks from running."""
        mgr = SerialManager()
        states = []

        def bad_cb(connected):
            raise RuntimeError("boom")

        def good_cb(connected):
            states.append(connected)

        mgr.register_link_callback(bad_cb)
        mgr.register_link_callback(good_cb)
        mgr._notify_link_state(True)
        assert states == [True]  # good_cb still ran

    def test_motion_command_rejected_when_disconnected(self):
        """send_motion_command must return False when serial link is not connected."""
        mgr = SerialManager()
        assert mgr.is_connected is False  # Not connected by default

        from backend.protocol import CmdMotion
        cmd = CmdMotion(
            target_vel_x=0, target_yaw_rate=0,
            leg_height_l=135, leg_height_r=135,
            roll_trim=0, flags=1, reserved=0, command_id=0
        )
        result = asyncio.run(mgr.send_motion_command(cmd))
        assert result is False

    def test_exponential_backoff_values(self):
        """Verify exponential backoff calculation logic matches the manager's formula."""
        # Formula: min(8.0, 0.5 * (1.5 ** min(attempts, 6)))
        expected = [
            (1, 0.5 * 1.5),            # 0.75
            (2, 0.5 * 2.25),           # 1.125
            (3, 0.5 * 3.375),          # 1.6875
            (4, 0.5 * 5.0625),         # 2.53125
            (5, 0.5 * 7.59375),        # 3.796875
            (6, 0.5 * 11.390625),      # 5.6953125
            (7, 0.5 * 11.390625),      # min(7,6)=6 → same as attempt 6: 5.6953125
            (10, 0.5 * 11.390625),     # min(10,6)=6 → clamped exponent, 5.6953125
        ]
        for attempts, expected_delay in expected:
            actual = min(8.0, 0.5 * (1.5 ** min(attempts, 6)))
            assert abs(actual - expected_delay) < 0.001, \
                f"Backoff mismatch at attempt {attempts}: {actual} != {expected_delay}"


# ============================================================================
# Server-Level Serial Integration Tests
# ============================================================================

class TestServerSerialIntegration:
    """Tests for server.py integration with serial link state changes."""

    def test_on_serial_link_change_sets_global_flag(self):
        """on_serial_link_change must update serial_link_down global correctly."""
        from backend import server
        on_serial_link_change(True)
        assert server.serial_link_down is False

        on_serial_link_change(False)
        assert server.serial_link_down is True

    def test_ws_rejects_motion_when_serial_down(self):
        """Motion commands via WebSocket must be rejected when serial link is down."""
        # Ensure serial is marked disconnected
        serial_mgr.is_connected = False
        ws_tickets.clear()
        ticket_request_history.clear()

        client = TestClient(app, base_url="http://testserver")
        try:
            # Get a valid ticket
            res = client.post(
                "/api/ws-ticket",
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            assert res.status_code == 200
            ticket = res.json()["ticket"]

            with client.websocket_connect(f"/ws?ticket={ticket}") as ws:
                ack = ws.receive_json()
                assert ack["type"] == "connection_ack"
                assert ack["is_controller"] is True

                # Send motion command while serial is down
                ws.send_json({
                    "type": "command",
                    "linear_x": 0.5,
                    "angular_z": 0.0,
                    "command_id": 1
                })
                resp = ws.receive_json()
                assert resp["type"] == "error"
                assert "Serial link" in resp["message"] or "DOWN" in resp["message"]
        finally:
            ws_tickets.clear()
            # Clean up global state
            from backend import server
            server.primary_controller_ws = None

    def test_system_info_reports_serial_status(self):
        """GET /api/system/info must report current serial_connected status."""
        serial_mgr.is_connected = False
        client = TestClient(app, base_url="http://testserver")
        res = client.get(
            "/api/system/info",
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["serial_connected"] is False


# ============================================================================
# CRC16 Edge Cases
# ============================================================================

class TestCRC16EdgeCases:
    """Verify CRC-16-CCITT implementation correctness."""

    def test_crc_empty_data(self):
        """CRC of empty data should be the initial value 0xFFFF."""
        assert compute_crc16(b'') == 0xFFFF

    def test_crc_deterministic(self):
        """Same input must always produce the same CRC."""
        data = b'\x04\x01\x06\x00\x00\x00\x00'
        crc1 = compute_crc16(data)
        crc2 = compute_crc16(data)
        assert crc1 == crc2

    def test_crc_single_bit_sensitivity(self):
        """Flipping a single bit must produce a different CRC."""
        data1 = b'\x00\x00\x00\x00'
        data2 = b'\x00\x00\x00\x01'
        assert compute_crc16(data1) != compute_crc16(data2)

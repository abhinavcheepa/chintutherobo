"""Unit tests for serial protocol framing, CRC16 checksum, and stream parser."""

import pytest
import struct
from backend.protocol import (
    compute_crc16, encode_frame, StreamParser,
    CmdMotion, Telemetry, Heartbeat, AckNack,
    MSG_CMD_MOTION, MSG_TELEMETRY, MSG_HEARTBEAT, MSG_ACK_NACK
)


def test_crc16_known_vector():
    """Verify CRC-16-CCITT implementation against known reference values."""
    # Test vector: ASCII '123456789' with poly 0x1021, init 0xFFFF -> 0x29B1
    data = b"123456789"
    crc = compute_crc16(data)
    assert crc == 0x29B1, f"Expected 0x29B1, got 0x{crc:04X}"


def test_cmd_motion_pack_unpack():
    """Verify CmdMotion serialization and deserialization."""
    original = CmdMotion(
        target_vel_x=450,
        target_yaw_rate=-1200,
        leg_height_l=135,
        leg_height_r=130,
        roll_trim=50,
        flags=1,
        reserved=0,
        command_id=42
    )

    packed = original.pack()
    assert len(packed) == 14

    restored = CmdMotion.unpack(packed)
    assert restored.target_vel_x == 450
    assert restored.target_yaw_rate == -1200
    assert restored.leg_height_l == 135
    assert restored.leg_height_r == 130
    assert restored.roll_trim == 50
    assert restored.flags == 1
    assert restored.command_id == 42


def test_telemetry_unpack():
    """Verify Telemetry payload decoding."""
    # Format: <hhhh iihh HH HBB HH 4B
    raw_bytes = struct.pack(
        "<hhhh iihh HH HBB HH 4B",
        150,     # pitch: 1.50 deg
        -25,     # pitch rate: -0.25 dps
        5,       # roll: 0.05 deg
        0,       # yaw rate: 0.00 dps
        10000,   # wheel_pos_l
        10005,   # wheel_pos_r
        450,     # wheel_vel_l
        450,     # wheel_vel_r
        118,     # leg_pos_l
        118,     # leg_pos_r
        11850,   # 11.85V
        2,       # STATE_ARMED
        0,       # Error flags
        12,      # Jitter us
        101,     # last_cmd_id
        0, 0, 0, 0  # reserved
    )

    assert len(raw_bytes) == 36

    telem = Telemetry.unpack(raw_bytes)
    assert pytest.approx(telem.pitch_deg, 0.001) == 1.50
    assert pytest.approx(telem.pitch_rate_dps, 0.001) == -0.25
    assert telem.wheel_pos_l == 10000
    assert telem.v_batt_mv == 11850
    assert telem.state_code == 2
    assert telem.state_str == "ARMED"
    assert telem.last_cmd_id == 101


def test_stream_parser_clean_frame():
    """Verify StreamParser decodes a cleanly encoded frame."""
    payload = Heartbeat(timestamp_ms=123456).pack()
    frame = encode_frame(MSG_HEARTBEAT, seq=10, payload=payload)

    parser = StreamParser()
    frames = parser.parse(frame)

    assert len(frames) == 1
    msg_type, seq, rx_payload = frames[0]
    assert msg_type == MSG_HEARTBEAT
    assert seq == 10
    hb = Heartbeat.unpack(rx_payload)
    assert hb.timestamp_ms == 123456


def test_stream_parser_noise_resilience():
    """Verify StreamParser discards noise and captures valid frame."""
    garbage = b"\x00\xFF\xAA\x00\x12\x34\xAA\x54"
    valid_payload = bytes([1, 2, 3, 4])
    frame = encode_frame(MSG_CMD_MOTION, seq=5, payload=valid_payload)
    trailing_junk = b"\xEE\xAA"

    stream = garbage + frame + trailing_junk

    parser = StreamParser()
    frames = parser.parse(stream)

    assert len(frames) == 1
    msg_type, seq, payload = frames[0]
    assert msg_type == MSG_CMD_MOTION
    assert seq == 5
    assert payload == valid_payload


def test_stream_parser_corrupt_crc_rejected():
    """Verify that corrupt frames with invalid CRC are rejected."""
    payload = bytes([10, 20, 30])
    frame = bytearray(encode_frame(MSG_CMD_MOTION, seq=1, payload=payload))
    # Corrupt payload byte
    frame[5] ^= 0xFF

    parser = StreamParser()
    frames = parser.parse(bytes(frame))
    assert len(frames) == 0


def test_serial_manager_dispatch_telemetry_regression():
    """Verify that _dispatch_frame for telemetry updates last_rx_time without NameError."""
    from backend.serial_manager import SerialManager
    manager = SerialManager()
    assert manager.last_rx_time == 0.0

    raw_bytes = struct.pack(
        "<hhhh iihh HH HBB HH 4B",
        150, -25, 5, 0,
        10000, 10005, 450, 450,
        118, 118,
        1180, 12, 10,
        0, 0,
        0, 0, 0, 0
    )
    manager._dispatch_frame(MSG_TELEMETRY, 1, raw_bytes)
    assert manager.last_rx_time > 0.0
    assert manager.latest_telemetry is not None
    assert abs(manager.latest_telemetry.pitch_deg - 1.50) < 1e-4

"""Asyncio Serial Interface Manager with Auto-Reconnect and Heartbeat Generator."""

import asyncio
import logging
import time
import serial
try:
    import serial_asyncio
except ImportError:
    serial_asyncio = None
from typing import Optional, Callable, List
from backend.config import (
    SERIAL_PORT, SERIAL_BAUD, SERIAL_RECONNECT_DELAY_S, SERIAL_HEARTBEAT_INTERVAL_S
)
from backend.protocol import (
    StreamParser, encode_frame, MSG_CMD_MOTION, MSG_TELEMETRY, MSG_HEARTBEAT,
    MSG_CMD_ARM_STATE, MSG_CONFIG_PID_SET, MSG_CONFIG_SAVE, MSG_EMERGENCY_STOP,
    MSG_ACK_NACK, CmdMotion, Telemetry, Heartbeat, CmdArmState, ConfigPidSet, AckNack
)

logger = logging.getLogger("SerialManager")


class SerialManager:
    """Manages full-duplex framed binary communications with Arduino Mega."""

    def __init__(self, port: str = SERIAL_PORT, baud: int = SERIAL_BAUD):
        self.port = port
        self.baud = baud
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.is_connected = False
        self._tx_seq = 0
        self._parser = StreamParser()

        # Telemetry callbacks
        self.telemetry_callbacks: List[Callable[[Telemetry], None]] = []
        self.ack_callbacks: List[Callable[[AckNack], None]] = []
        self.link_callbacks: List[Callable[[bool], None]] = []

        self._running = False
        self._tasks: List[asyncio.Task] = []
        self.latest_telemetry: Optional[Telemetry] = None
        self.last_rx_time: float = 0.0
        self.reconnect_attempts = 0

    async def start(self) -> None:
        """Starts background worker tasks."""
        self._running = True
        self._tasks.append(asyncio.create_task(self._connection_supervisor()))
        self._tasks.append(asyncio.create_task(self._heartbeat_worker()))

    async def stop(self) -> None:
        """Stops all tasks and closes the connection."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        await self._disconnect()

    def register_telemetry_callback(self, cb: Callable[[Telemetry], None]) -> None:
        self.telemetry_callbacks.append(cb)

    def register_ack_callback(self, cb: Callable[[AckNack], None]) -> None:
        self.ack_callbacks.append(cb)

    def register_link_callback(self, cb: Callable[[bool], None]) -> None:
        self.link_callbacks.append(cb)

    def _notify_link_state(self, connected: bool) -> None:
        for cb in self.link_callbacks:
            try:
                cb(connected)
            except Exception as e:
                logger.error("Error in link callback: %s", e)

    async def _disconnect(self) -> None:
        was_connected = self.is_connected
        self.is_connected = False
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.debug("Error while closing writer: %s", e)
            self.writer = None
            self.reader = None
        if was_connected:
            logger.warning("Serial link lost! Notifying supervisor and UI.")
            self._notify_link_state(False)

    async def _connection_supervisor(self) -> None:
        """Supervises serial connection and triggers auto-reconnect with exponential backoff."""
        candidate_ports = [self.port, "/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyUSB1", "COM3", "COM4", "COM5"]
        # Deduplicate while preserving order
        unique_candidates = list(dict.fromkeys(candidate_ports))

        while self._running:
            if not self.is_connected:
                connected = False
                for port_candidate in unique_candidates:
                    try:
                        logger.info("Attempting connection to %s at %d baud...", port_candidate, self.baud)
                        if serial_asyncio is None:
                            raise serial.SerialException("serial_asyncio module not installed")
                        self.reader, self.writer = await serial_asyncio.open_serial_connection(
                            url=port_candidate,
                            baudrate=self.baud,
                            timeout=1.0
                        )
                        self.port = port_candidate
                        self.is_connected = True
                        connected = True
                        self.reconnect_attempts = 0
                        logger.info("Serial connection established with Mega 2560 on %s", self.port)
                        self._notify_link_state(True)
                        await self._read_loop()
                        break
                    except (serial.SerialException, OSError, asyncio.CancelledError) as e:
                        logger.debug("Port candidate %s unavailable: %s", port_candidate, e)
                        await self._disconnect()

                if not connected:
                    self.reconnect_attempts += 1
                    # Exponential backoff capped at 8.0s: 0.5s * 1.5^(attempts)
                    delay = min(8.0, 0.5 * (1.5 ** min(self.reconnect_attempts, 6)))
                    await asyncio.sleep(delay)
            else:
                await asyncio.sleep(0.5)

    async def _read_loop(self) -> None:
        """Continuously reads bytes from serial port and dispatches frames."""
        while self._running and self.is_connected and self.reader:
            try:
                chunk = await self.reader.read(128)
                if not chunk:
                    await asyncio.sleep(0.005)
                    continue

                frames = self._parser.parse(chunk)
                for msg_type, seq, payload in frames:
                    self._dispatch_frame(msg_type, seq, payload)

            except Exception as e:
                logger.error("Error in read loop: %s", e)
                break

        await self._disconnect()

    def _dispatch_frame(self, msg_type: int, seq: int, payload: bytes) -> None:
        """Parses decoded frames into typed payloads."""
        if msg_type == MSG_TELEMETRY:
            try:
                telem = Telemetry.unpack(payload)
                self.latest_telemetry = telem
                self.last_rx_time = time.time()
                for cb in self.telemetry_callbacks:
                    try:
                        cb(telem)
                    except Exception as cb_err:
                        logger.error("Error in telemetry callback: %s", cb_err)
            except Exception as e:
                logger.error("Failed to unpack telemetry payload: %s", e)

        elif msg_type == MSG_ACK_NACK:
            try:
                ack = AckNack.unpack(payload)
                logger.debug("Received ACK_NACK: type=%d, status=%d, code=%d", ack.acked_msg_type, ack.status, ack.error_code)
                for cb in self.ack_callbacks:
                    try:
                        cb(ack)
                    except Exception as cb_err:
                        logger.error("Error in ACK callback: %s", cb_err)
            except Exception as e:
                logger.error("Failed to unpack ACK_NACK payload: %s", e)

    async def send_frame(self, msg_type: int, payload: bytes) -> bool:
        """Thread-safe frame transmitter."""
        if not self.is_connected or not self.writer:
            return False

        try:
            self._tx_seq = (self._tx_seq + 1) & 0xFF
            frame = encode_frame(msg_type, self._tx_seq, payload)
            self.writer.write(frame)
            await self.writer.drain()
            return True
        except Exception as e:
            logger.error("Failed to transmit frame type 0x%02X: %s", msg_type, e)
            await self._disconnect()
            return False

    async def send_motion_command(self, cmd: CmdMotion) -> bool:
        if not self.is_connected:
            logger.warning("Rejected motion command: serial link to Mega is DOWN.")
            return False
        return await self.send_frame(MSG_CMD_MOTION, cmd.pack())

    async def send_arm_state(self, state: int, force: bool = False) -> bool:
        cmd = CmdArmState(requested_state=state, force=1 if force else 0)
        return await self.send_frame(MSG_CMD_ARM_STATE, cmd.pack())

    async def send_pid_config(self, cfg: ConfigPidSet) -> bool:
        return await self.send_frame(MSG_CONFIG_PID_SET, cfg.pack())

    async def send_save_eeprom(self) -> bool:
        return await self.send_frame(MSG_CONFIG_SAVE, b"")

    async def send_estop(self, reason: int = 1) -> bool:
        return await self.send_frame(MSG_EMERGENCY_STOP, bytes([reason, 0]))

    async def _heartbeat_worker(self) -> None:
        """Sends periodic keep-alive heartbeat packets."""
        while self._running:
            if self.is_connected:
                now_ms = int(asyncio.get_event_loop().time() * 1000) & 0xFFFFFFFF
                hb = Heartbeat(timestamp_ms=now_ms)
                await self.send_frame(MSG_HEARTBEAT, hb.pack())
            await asyncio.sleep(SERIAL_HEARTBEAT_INTERVAL_S)

"""Line-based serial protocol client for Arduino Mega."""
from __future__ import annotations
import threading
import time
from typing import Optional, Any

class SerialManager:
    def __init__(self, port: str, baud_rate: int = 115200,
                 timeout_s: float = 0.25):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout_s = timeout_s
        self._serial: Optional[Any] = None
        self._lock = threading.Lock()
        self._request_id = 0
        self.last_message_time = 0.0

    @property
    def connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self) -> None:
        import serial  # Imported here so offline unit tests do not require hardware dependencies.
        self._serial = serial.Serial(self.port, self.baud_rate,
                                     timeout=self.timeout_s, write_timeout=1)
        time.sleep(2.0)  # Mega may reset when serial opens
        self._serial.reset_input_buffer()

    def close(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def next_id(self) -> str:
        self._request_id = (self._request_id + 1) % 1_000_000
        return str(self._request_id)

    def send_command(self, command: str) -> str:
        allowed = {"STATUS", "STAND", "STOP", "CALIBRATE", "BALANCE"}
        if command not in allowed:
            raise ValueError(f"Unsupported command: {command}")
        if not self.connected:
            raise ConnectionError("Arduino serial connection is not open")
        request_id = self.next_id()
        message = f"{command},{request_id}\n".encode("ascii")
        with self._lock:
            self._serial.write(message)
            self._serial.flush()
        return request_id

    def read_message(self) -> Optional[str]:
        if not self.connected:
            raise ConnectionError("Arduino serial connection is not open")
        raw = self._serial.readline()
        if not raw:
            return None
        try:
            message = raw.decode("ascii", errors="strict").strip()
        except UnicodeDecodeError:
            return None
        if not message or len(message) > 160:
            return None
        self.last_message_time = time.monotonic()
        return message

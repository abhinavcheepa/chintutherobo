"""High-level robot state requests; no direct motor control on the Pi."""
from __future__ import annotations
from enum import Enum
from typing import Optional
from serial_manager import SerialManager

class RobotMode(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    STAND_REQUESTED = "STAND_REQUESTED"
    STANDING_COMMAND_SENT = "STANDING_COMMAND_SENT"
    BALANCE_DISABLED = "BALANCE_DISABLED"
    FAULT = "FAULT"
    UNKNOWN = "UNKNOWN"

class RobotController:
    def __init__(self, serial_manager: SerialManager):
        self.serial = serial_manager
        self.mode = RobotMode.DISCONNECTED
        self.last_status: Optional[str] = None

    def request_status(self) -> str:
        return self.serial.send_command("STATUS")

    def request_stand(self) -> str:
        if not self.serial.connected:
            raise ConnectionError("Cannot request standing: Arduino disconnected")
        self.mode = RobotMode.STAND_REQUESTED
        return self.serial.send_command("STAND")

    def request_calibration(self) -> str:
        return self.serial.send_command("CALIBRATE")

    def request_stop(self) -> str:
        # Software stop request; physical emergency stop remains separate.
        return self.serial.send_command("STOP")

    def request_balance(self) -> str:
        # Firmware deliberately rejects this until mechanical mapping is verified.
        return self.serial.send_command("BALANCE")

    def consume_message(self, message: str) -> None:
        self.last_status = message
        fields = message.split(",")
        if fields and fields[0] == "STATUS" and len(fields) >= 3:
            state = fields[2]
            self.mode = next((m for m in RobotMode if m.value == state),
                             RobotMode.UNKNOWN)
        elif fields and fields[0] == "BOOT" and len(fields) >= 4:
            self.mode = RobotMode.IDLE if fields[2] == "READY" else RobotMode.FAULT

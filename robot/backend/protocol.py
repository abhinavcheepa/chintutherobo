"""Binary framed serial protocol encoder, decoder, and dataclasses."""

from __future__ import annotations
import struct
from dataclasses import dataclass
from typing import Optional, Tuple, List

SYNC_0 = 0xAA
SYNC_1 = 0x55

# Message Identifiers
MSG_CMD_MOTION = 0x01
MSG_TELEMETRY = 0x02
MSG_CONFIG_PID_SET = 0x03
MSG_CONFIG_PID_GET = 0x04
MSG_CMD_ARM_STATE = 0x05
MSG_HEARTBEAT = 0x06
MSG_ACK_NACK = 0x07
MSG_CONFIG_SAVE = 0x08
MSG_EMERGENCY_STOP = 0xFF

# Robot State Constants
STATE_DISARMED = 0
STATE_CALIBRATING = 1
STATE_ARMED = 2
STATE_FAULT = 3

STATE_NAMES = {
    STATE_DISARMED: "DISARMED",
    STATE_CALIBRATING: "CALIBRATING",
    STATE_ARMED: "ARMED",
    STATE_FAULT: "FAULT"
}

# Fault bitmask constants
ERROR_FLAG_NONE = 0x00
ERROR_FLAG_TILT = 0x01
ERROR_FLAG_TIMEOUT = 0x02
ERROR_FLAG_LOW_BATT = 0x04
ERROR_FLAG_MOTOR = 0x08
ERROR_FLAG_ESTOP = 0x10
ERROR_FLAG_SENSOR = 0x20


def compute_crc16(data: bytes) -> int:
    """Calculates CRC-16-CCITT (poly 0x1021, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8) & 0xFFFF
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


@dataclass
class CmdMotion:
    target_vel_x: int  # mm/s (-1000 to +1000)
    target_yaw_rate: int  # mrad/s (-3141 to +3141)
    leg_height_l: int  # mm (80 to 180)
    leg_height_r: int  # mm (80 to 180)
    roll_trim: int  # mrad (-350 to +350)
    flags: int = 1  # Bit 0: balance enable
    reserved: int = 0
    command_id: int = 0

    _FMT = "<hhHHhBBH"

    def pack(self) -> bytes:
        return struct.pack(
            self._FMT,
            self.target_vel_x,
            self.target_yaw_rate,
            self.leg_height_l,
            self.leg_height_r,
            self.roll_trim,
            self.flags,
            self.reserved,
            self.command_id
        )

    @classmethod
    def unpack(cls, data: bytes) -> CmdMotion:
        vals = struct.unpack(cls._FMT, data)
        return cls(*vals)


@dataclass
class Telemetry:
    pitch_deg: float
    pitch_rate_dps: float
    roll_deg: float
    yaw_rate_dps: float
    wheel_pos_l: int
    wheel_pos_r: int
    wheel_vel_l: int
    wheel_vel_r: int
    leg_pos_l: int
    leg_pos_r: int
    v_batt_mv: int
    state_code: int
    state_str: str
    error_flags: int
    loop_jitter_us: int
    last_cmd_id: int

    _FMT = "<hhhh iihh HH HBB HH 4B"

    @classmethod
    def unpack(cls, data: bytes) -> Telemetry:
        raw = struct.unpack(cls._FMT, data)
        pitch_deg = raw[0] / 100.0
        pitch_rate_dps = raw[1] / 100.0
        roll_deg = raw[2] / 100.0
        yaw_rate_dps = raw[3] / 100.0
        wheel_pos_l = raw[4]
        wheel_pos_r = raw[5]
        wheel_vel_l = raw[6]
        wheel_vel_r = raw[7]
        leg_pos_l = raw[8]
        leg_pos_r = raw[9]
        v_batt_mv = raw[10]
        state_code = raw[11]
        error_flags = raw[12]
        loop_jitter_us = raw[13]
        last_cmd_id = raw[14]

        return cls(
            pitch_deg=pitch_deg,
            pitch_rate_dps=pitch_rate_dps,
            roll_deg=roll_deg,
            yaw_rate_dps=yaw_rate_dps,
            wheel_pos_l=wheel_pos_l,
            wheel_pos_r=wheel_pos_r,
            wheel_vel_l=wheel_vel_l,
            wheel_vel_r=wheel_vel_r,
            leg_pos_l=leg_pos_l,
            leg_pos_r=leg_pos_r,
            v_batt_mv=v_batt_mv,
            state_code=state_code,
            state_str=STATE_NAMES.get(state_code, f"UNKNOWN({state_code})"),
            error_flags=error_flags,
            loop_jitter_us=loop_jitter_us,
            last_cmd_id=last_cmd_id
        )


@dataclass
class ConfigPidSet:
    controller_id: int  # 0: Pitch, 1: Vel, 2: Yaw
    save_to_eeprom: int  # 1 = yes
    kp: float
    ki: float
    kd: float
    k_ff: float
    out_min: float
    out_max: float

    _FMT = "<BBffffff"

    def pack(self) -> bytes:
        return struct.pack(
            self._FMT,
            self.controller_id,
            self.save_to_eeprom,
            self.kp,
            self.ki,
            self.kd,
            self.k_ff,
            self.out_min,
            self.out_max
        )


@dataclass
class CmdArmState:
    requested_state: int  # 0: DISARM, 1: CALIB, 2: ARM, 3: CLEAR_FAULT
    force: int = 0

    _FMT = "<BB"

    def pack(self) -> bytes:
        return struct.pack(self._FMT, self.requested_state, self.force)


@dataclass
class Heartbeat:
    timestamp_ms: int

    _FMT = "<I"

    def pack(self) -> bytes:
        return struct.pack(self._FMT, self.timestamp_ms)

    @classmethod
    def unpack(cls, data: bytes) -> Heartbeat:
        (ts,) = struct.unpack(cls._FMT, data)
        return cls(ts)


@dataclass
class AckNack:
    acked_msg_type: int
    status: int
    error_code: int

    _FMT = "<BBH"

    @classmethod
    def unpack(cls, data: bytes) -> AckNack:
        vals = struct.unpack(cls._FMT, data)
        return cls(*vals)


def encode_frame(msg_type: int, seq: int, payload: bytes) -> bytes:
    """Encodes a payload into a framed serial packet with CRC-16."""
    length = len(payload)
    if length > 64:
        raise ValueError(f"Payload size {length} exceeds maximum frame limit of 64 bytes")

    header = bytes([SYNC_0, SYNC_1, length, seq & 0xFF, msg_type])
    crc_data = bytes([length, seq & 0xFF, msg_type]) + payload
    crc = compute_crc16(crc_data)
    crc_bytes = struct.pack("<H", crc)
    return header + payload + crc_bytes


class StreamParser:
    """Stateful streaming byte-by-byte parser for framed binary packets."""

    STATE_WAIT_SYNC0 = 0
    STATE_WAIT_SYNC1 = 1
    STATE_WAIT_LEN = 2
    STATE_WAIT_SEQ = 3
    STATE_WAIT_TYPE = 4
    STATE_READ_PAYLOAD = 5
    STATE_WAIT_CRC_L = 6
    STATE_WAIT_CRC_H = 7

    def __init__(self):
        self._state = self.STATE_WAIT_SYNC0
        self._len = 0
        self._seq = 0
        self._type = 0
        self._payload = bytearray()
        self._crc_received = 0

    def parse(self, chunk: bytes) -> List[Tuple[int, int, bytes]]:
        """Consumes a byte chunk and yields any complete, validated (msg_type, seq, payload) tuples."""
        valid_frames = []
        for b in chunk:
            if self._state == self.STATE_WAIT_SYNC0:
                if b == SYNC_0:
                    self._state = self.STATE_WAIT_SYNC1

            elif self._state == self.STATE_WAIT_SYNC1:
                if b == SYNC_1:
                    self._state = self.STATE_WAIT_LEN
                elif b == SYNC_0:
                    self._state = self.STATE_WAIT_SYNC1  # Consecutive 0xAA 0xAA 0x55 resync
                else:
                    self._state = self.STATE_WAIT_SYNC0

            elif self._state == self.STATE_WAIT_LEN:
                self._len = b
                if self._len > 64:
                    self._state = self.STATE_WAIT_SYNC0
                else:
                    self._state = self.STATE_WAIT_SEQ

            elif self._state == self.STATE_WAIT_SEQ:
                self._seq = b
                self._state = self.STATE_WAIT_TYPE

            elif self._state == self.STATE_WAIT_TYPE:
                self._type = b
                self._payload = bytearray()
                if self._len == 0:
                    self._state = self.STATE_WAIT_CRC_L
                else:
                    self._state = self.STATE_READ_PAYLOAD

            elif self._state == self.STATE_READ_PAYLOAD:
                self._payload.append(b)
                if len(self._payload) >= self._len:
                    self._state = self.STATE_WAIT_CRC_L

            elif self._state == self.STATE_WAIT_CRC_L:
                self._crc_received = b
                self._state = self.STATE_WAIT_CRC_H

            elif self._state == self.STATE_WAIT_CRC_H:
                self._crc_received |= (b << 8)
                # Validate CRC
                crc_data = bytes([self._len, self._seq, self._type]) + bytes(self._payload)
                expected_crc = compute_crc16(crc_data)

                if expected_crc == self._crc_received:
                    valid_frames.append((self._type, self._seq, bytes(self._payload)))

                self._state = self.STATE_WAIT_SYNC0

        return valid_frames

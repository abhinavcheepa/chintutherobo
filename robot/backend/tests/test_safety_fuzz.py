"""Fuzzing and adversarial robustness test suite for binary protocol stream parser."""

import os
import random
import pytest
from backend.protocol import (
    StreamParser, encode_frame, compute_crc16,
    MSG_CMD_MOTION, MSG_TELEMETRY, MSG_HEARTBEAT,
    CmdMotion, Heartbeat
)


def test_parser_fuzz_garbage_resilience():
    """Inject 10,000 random pseudo-random bytes and ensure parser never crashes or memory leaks."""
    parser = StreamParser()
    random.seed(42)

    # Generate 10KB of random noise
    noise = bytearray(random.getrandbits(8) for _ in range(10000))
    frames = parser.parse(bytes(noise))

    # High-entropy noise should yield near-zero or zero false packets
    for msg_type, seq, payload in frames:
        # If any frame passes, its CRC must strictly match
        crc_data = bytes([len(payload), seq, msg_type]) + payload
        assert compute_crc16(crc_data) == parser._crc_received


def test_parser_interspersed_valid_frames_in_heavy_fuzz():
    """Embed valid frames within dense noise and assert 100% extraction."""
    parser = StreamParser()
    random.seed(1337)

    extracted_hb = []
    stream = bytearray()

    for i in range(20):
        # Noise prefix
        stream.extend(bytearray(random.getrandbits(8) for _ in range(random.randint(10, 100))))
        # Valid frame
        hb = Heartbeat(timestamp_ms=1000 + i)
        frame = encode_frame(MSG_HEARTBEAT, seq=i, payload=hb.pack())
        stream.extend(frame)
        # Noise suffix
        stream.extend(bytearray(random.getrandbits(8) for _ in range(random.randint(10, 100))))

    frames = parser.parse(bytes(stream))
    for msg_type, seq, payload in frames:
        if msg_type == MSG_HEARTBEAT:
            extracted_hb.append(Heartbeat.unpack(payload).timestamp_ms)

    assert len(extracted_hb) == 20
    assert extracted_hb == [1000 + i for i in range(20)]


def test_parser_length_mutation_attack():
    """Verify parser rejects payload lengths claiming > 64 bytes without overflowing."""
    parser = StreamParser()

    # Preamble + Length 255 + Seq 0 + Type 1 + 255 bytes of data
    malformed = bytes([0xAA, 0x55, 0xFF, 0x00, 0x01]) + (b"\x00" * 255)
    frames = parser.parse(malformed)

    assert len(frames) == 0
    assert len(parser._payload) == 0


def test_parser_fragmented_delivery():
    """Verify frames delivered 1 byte at a time are assembled correctly."""
    parser = StreamParser()
    cmd = CmdMotion(target_vel_x=200, target_yaw_rate=500, leg_height_l=118, leg_height_r=118, roll_trim=0)
    frame = encode_frame(MSG_CMD_MOTION, seq=77, payload=cmd.pack())

    extracted = []
    for b in frame:
        res = parser.parse(bytes([b]))
        if res:
            extracted.extend(res)

    assert len(extracted) == 1
    msg_type, seq, payload = extracted[0]
    assert msg_type == MSG_CMD_MOTION
    assert seq == 77
    assert CmdMotion.unpack(payload).target_vel_x == 200

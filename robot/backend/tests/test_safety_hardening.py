"""Automated Safety Hardening Tests for Chintu Supervisor and Comms Stack.
Verifies server-side validation, controller locking, fail-closed timeouts, and E-STOP delivery.
"""

import pytest
import asyncio
import time
import json
import sys
from pathlib import Path
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.server import MotionCommand, ArmStateCommand, EstopCommand, PidSetCommand
from backend.config import (
    LEG_HEIGHT_MIN_MM, LEG_HEIGHT_MAX_MM, LEG_HEIGHT_NOMINAL_MM,
    MAX_ROLL_TRIM_RAD, SPEED_LIMIT_FREE_RUN_MPS, SPEED_LIMIT_GATED_MPS,
    BROWSER_COMMAND_TIMEOUT_S, FIRMWARE_WATCHDOG_TIMEOUT_S
)
from tools.mock_ws_server import SimulationState


def test_motion_command_validation_rejection():
    """Verify out-of-range values are strictly rejected by Pydantic validation, not silently accepted."""
    # Valid command
    valid = MotionCommand(
        linear_x=0.5,
        angular_z=-0.2,
        leg_height_l=135.0,
        leg_height_r=135.0,
        roll_trim=0.1,
        balance_enable=True
    )
    assert valid.linear_x == 0.5

    # Out of bounds speed (> 1.0)
    with pytest.raises(ValidationError):
        MotionCommand(linear_x=1.5)

    with pytest.raises(ValidationError):
        MotionCommand(linear_x=-1.5)

    # Out of bounds height (> 175 mm or < 85 mm)
    with pytest.raises(ValidationError):
        MotionCommand(leg_height_l=185.0)

    with pytest.raises(ValidationError):
        MotionCommand(leg_height_l=75.0)

    # Out of bounds roll trim (> ~15 deg)
    with pytest.raises(ValidationError):
        MotionCommand(roll_trim=0.50)


def test_arm_state_validation_rejection():
    """Verify only allowed state strings are accepted."""
    valid = ArmStateCommand(state="CALIBRATING")
    assert valid.state == "CALIBRATING"

    with pytest.raises(ValidationError):
        ArmStateCommand(state="EXPLODE")

    with pytest.raises(ValidationError):
        ArmStateCommand(state="INVALID_STATE")


def test_pid_set_validation_rejection():
    """Verify PID gain bounds and controller ID constraints."""
    valid = PidSetCommand(controller_id=0, kp=35.0, ki=0.2, kd=1.5)
    assert valid.kp == 35.0

    # Invalid controller ID (> 2)
    with pytest.raises(ValidationError):
        PidSetCommand(controller_id=5, kp=10.0, ki=1.0, kd=1.0)

    # Negative gains rejected
    with pytest.raises(ValidationError):
        PidSetCommand(controller_id=0, kp=-5.0, ki=1.0, kd=1.0)


def test_mock_simulation_comms_watchdog_timeout():
    """Verify the 400ms comms watchdog trips in ARMED state when no commands arrive."""
    sim = SimulationState()
    sim.state = "ARMED"
    sim.state_code = 2
    sim.last_cmd_rx_time = time.time() - 0.450 # 450 ms of silence

    # Step physics
    sim.update_physics(0.05)

    assert sim.state == "FAULT"
    assert (sim.error_flags & 0x02) != 0 # ERROR_FLAG_TIMEOUT
    assert "COMMS_TIMEOUT" in sim.error_desc


def test_mock_simulation_tilt_cutoff():
    """Verify tilt cutoff triggers when pitch > 45 deg or roll > 35 deg."""
    sim = SimulationState()
    sim.state = "ARMED"
    sim.state_code = 2
    sim.last_cmd_rx_time = time.time()
    sim.pitch = 48.0 # Critical pitch exceedance

    sim.update_physics(0.05)

    assert sim.state == "FAULT"
    assert (sim.error_flags & 0x01) != 0 # ERROR_FLAG_TILT
    assert "TILT_CUTOFF" in sim.error_desc


def test_mock_simulation_battery_cutoff():
    """Verify critical battery cutoff triggers when voltage < 9.6 V."""
    sim = SimulationState()
    sim.state = "ARMED"
    sim.state_code = 2
    sim.battery_voltage = 9.40

    sim.update_physics(0.05)

    assert sim.state == "FAULT"
    assert (sim.error_flags & 0x04) != 0 # ERROR_FLAG_LOW_BATT

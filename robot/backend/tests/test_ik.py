"""Unit tests for planar leg inverse kinematics solver and forward kinematics."""

import pytest
import sys
from pathlib import Path

# Add project root to path for tool imports
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT))

from tools.ik_solver import BipedKinematics


def test_nominal_height_ik():
    """Verify nominal 135mm stance calculation (knee flexed ~105 deg)."""
    ik = BipedKinematics()
    sol = ik.solve_leg(height_mm=135.0, offset_x_mm=0.0)

    assert sol.reachable is True
    assert pytest.approx(sol.actual_height_mm, 0.5) == 135.0
    # Knee must bend backwards (negative angle)
    assert sol.knee_pitch_deg < 0.0
    # Hip pitch must be positive to compensate
    assert sol.hip_pitch_deg > 0.0


def test_every_ui_selectable_height_has_valid_ik():
    """Verify that EVERY single 1mm integer increment in UI range [85, 175] mm has a reachable IK solution."""
    ik = BipedKinematics(min_height=85.0, max_height=175.0)

    for h in range(85, 176):
        sol = ik.solve_leg(height_mm=float(h), offset_x_mm=0.0)
        assert sol.reachable is True, f"Height {h} mm failed IK reachability!"

        # FK consistency: computed actual height matches commanded height
        fk_x, fk_z = ik.forward_kinematics(sol.hip_pitch_deg, sol.knee_pitch_deg)
        assert pytest.approx(abs(fk_z), 0.1) == float(h)
        assert pytest.approx(abs(fk_x), 0.1) == 0.0


def test_out_of_bounds_clamping():
    """Verify solver clamps heights outside physical limits."""
    ik = BipedKinematics(min_height=85.0, max_height=175.0)

    sol_low = ik.solve_leg(height_mm=50.0)
    assert sol_low.reachable is False
    assert pytest.approx(sol_low.actual_height_mm, 0.5) == 85.0

    sol_high = ik.solve_leg(height_mm=250.0)
    assert sol_high.reachable is False
    assert pytest.approx(sol_high.actual_height_mm, 0.5) == 175.0


def test_roll_trim_symmetry():
    """Verify symmetrical opposite roll joint response for left vs right legs."""
    ik = BipedKinematics()
    sol_left = ik.solve_leg(height_mm=135.0, roll_trim_deg=10.0, is_left=True)
    sol_right = ik.solve_leg(height_mm=135.0, roll_trim_deg=10.0, is_left=False)

    assert sol_left.hip_roll_deg == 10.0
    assert sol_right.hip_roll_deg == -10.0

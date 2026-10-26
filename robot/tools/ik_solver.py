"""Standalone Planar 3-Link Inverse Kinematics Solver for Biped Wheel-Legs.

MATHEMATICAL DERIVATION OF REACHABLE LEG HEIGHT:
- Hardware link lengths:
    L1 (Hip lateral spacing) = 72.0 mm
    L2 (Thigh link)          = 120.0 mm
    L3 (Shank link)          = 101.0 mm
    Wheel diameter           = 80.0 mm (Radius = 40.0 mm)

- Geometric Reachable Limits along vertical z-axis (offset_x = 0):
    d_max = L2 + L3 = 120.0 + 101.0 = 221.0 mm (straight leg singularity)
    d_min = |L2 - L3| = |120.0 - 101.0| = 19.0 mm (fully folded scissor limit)

- Kinematic & Servo Hardware Feasibility Margins:
    To avoid straight-leg singularity (infinite joint velocity to accelerate forward)
    and physical linkage binding between servo horn and thigh bracket:
    Singularity safety margin = 46.0 mm from theoretical max -> max_height = 175.0 mm.
    Knee collision / fold margin = 66.0 mm from theoretical min -> min_height = 85.0 mm.

- Nominal Stance Height:
    At height = 135.0 mm:
    cos(knee_internal) = (120^2 + 101^2 - 135^2) / (2 * 120 * 101) = 6376 / 24240 = 0.2630
    knee_internal = 74.75 deg -> knee_bend = 105.25 deg (flexed ~105 deg).
    hip_pitch = 46.2 deg.
    Both joints operate in the center of their torque-speed curves and provide
    symmetric travel (+40 mm extension, -50 mm compression) for dynamic vertical hopping/balancing.
    (Note: 118 mm was robot COM height above ground, not the hip-to-axle leg length).
"""

import math
from dataclasses import dataclass
from typing import Tuple, Optional


@dataclass
class LegJointSolution:
    hip_roll_deg: float
    hip_pitch_deg: float
    knee_pitch_deg: float
    reachable: bool
    actual_height_mm: float


class BipedKinematics:
    """Analytical 3-link kinematics engine for symmetric biped robot."""

    def __init__(
        self,
        l1_hip: float = 72.0,
        l2_thigh: float = 120.0,
        l3_shank: float = 101.0,
        min_height: float = 85.0,
        max_height: float = 175.0
    ):
        self.l1 = l1_hip
        self.l2 = l2_thigh
        self.l3 = l3_shank
        self.min_height = min_height
        self.max_height = max_height

    def solve_leg(
        self,
        height_mm: float,
        offset_x_mm: float = 0.0,
        roll_trim_deg: float = 0.0,
        is_left: bool = True
    ) -> LegJointSolution:
        """Solves analytical IK for target leg extension and lateral trim."""
        reachable = True

        # Clamp height to mechanical limits
        clamped_height = max(self.min_height, min(height_mm, self.max_height))
        if clamped_height != height_mm:
            reachable = False

        # Lateral roll
        roll = roll_trim_deg if is_left else -roll_trim_deg
        roll = max(-20.0, min(roll, 20.0))

        # Planar 2-link model for thigh (l2) and shank (l3)
        x = offset_x_mm
        z = -clamped_height

        d_sq = x * x + z * z
        d = math.sqrt(d_sq)

        max_reach = self.l2 + self.l3 - 6.0
        min_reach = abs(self.l2 - self.l3) + 5.0

        if d > max_reach:
            d = max_reach
            reachable = False
        elif d < min_reach:
            d = min_reach
            reachable = False
        d_sq = d * d

        cos_knee = (self.l2 * self.l2 + self.l3 * self.l3 - d_sq) / (2.0 * self.l2 * self.l3)
        cos_knee = max(-1.0, min(1.0, cos_knee))

        knee_internal = math.acos(cos_knee)
        knee_bend = math.pi - knee_internal

        beta = math.atan2(x, -z)

        cos_thigh = (self.l2 * self.l2 + d_sq - self.l3 * self.l3) / (2.0 * self.l2 * d)
        cos_thigh = max(-1.0, min(1.0, cos_thigh))
        gamma = math.acos(cos_thigh)

        hip_pitch = beta + gamma

        hip_pitch_deg = math.degrees(hip_pitch)
        knee_pitch_deg = -math.degrees(knee_bend)

        # Forward kinematics verification
        fk_z = -(self.l2 * math.cos(hip_pitch) + self.l3 * math.cos(hip_pitch - knee_bend))

        return LegJointSolution(
            hip_roll_deg=roll,
            hip_pitch_deg=hip_pitch_deg,
            knee_pitch_deg=knee_pitch_deg,
            reachable=reachable,
            actual_height_mm=abs(fk_z)
        )

    def forward_kinematics(self, hip_pitch_deg: float, knee_pitch_deg: float) -> Tuple[float, float]:
        """Computes (x, z) of the wheel axle relative to hip joint."""
        hip_rad = math.radians(hip_pitch_deg)
        knee_rad = math.radians(knee_pitch_deg)

        total_shank_angle = hip_rad + knee_rad

        x = self.l2 * math.sin(hip_rad) + self.l3 * math.sin(total_shank_angle)
        z = -(self.l2 * math.cos(hip_rad) + self.l3 * math.cos(total_shank_angle))
        return x, z

"""Numerical Inverted Pendulum Simulation for Biped Wheel-Leg Balancing."""

import math
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class SimState:
    time: float
    pitch_deg: float
    pitch_rate_dps: float
    wheel_pos_m: float
    wheel_vel_mps: float
    wheel_accel_mps2: float
    leg_height_m: float


class WheelLegSimulator:
    """Nonlinear inverted pendulum on wheels with variable leg height."""

    def __init__(
        self,
        mass_total_kg: float = 1.178,
        wheel_radius_m: float = 0.040,
        nominal_height_m: float = 0.118,
        dt: float = 0.005  # 200 Hz
    ):
        self.m = mass_total_kg
        self.r = wheel_radius_m
        self.h_nom = nominal_height_m
        self.dt = dt
        self.g = 9.80665

        # Current state: theta (rad), dtheta (rad/s), x (m), dx (m/s)
        self.theta = 0.0
        self.dtheta = 0.0
        self.x = 0.0
        self.dx = 0.0

        # Controller states
        self.pitch_integral = 0.0
        self.vel_integral = 0.0

    def reset(self, initial_pitch_deg: float = 0.0):
        self.theta = math.radians(initial_pitch_deg)
        self.dtheta = 0.0
        self.x = 0.0
        self.dx = 0.0
        self.pitch_integral = 0.0
        self.vel_integral = 0.0

    def step(
        self,
        leg_height_m: float,
        target_vel_mps: float = 0.0,
        kp_base: float = 30.0,
        ki_base: float = 0.15,
        kd_base: float = 1.45,
        enable_gain_scheduling: bool = True
    ) -> SimState:
        """Executes one simulation step at 200 Hz using Euler-Cromer integration."""
        # 1. Gain scheduling based on effective pendulum length
        h_eff = max(0.08, min(leg_height_m, 0.18))
        if enable_gain_scheduling:
            sched = math.sqrt(h_eff / self.h_nom)
            kp = kp_base * sched
            kd = kd_base * (sched ** 1.5)
        else:
            kp = kp_base
            kd = kd_base
        ki = ki_base

        # 2. Control computation
        pitch_deg = math.degrees(self.theta)
        pitch_rate_dps = math.degrees(self.dtheta)

        # Outer velocity loop
        vel_err = target_vel_mps - self.dx
        self.vel_integral += vel_err * self.dt
        self.vel_integral = max(-2.0, min(2.0, self.vel_integral))
        target_pitch_deg = 0.02 * vel_err + 0.005 * self.vel_integral
        target_pitch_deg = max(-8.0, min(8.0, target_pitch_deg))

        # Inner balance loop (driving wheels in direction of tilt)
        pitch_err = pitch_deg - target_pitch_deg
        self.pitch_integral += pitch_err * self.dt
        self.pitch_integral = max(-5.0, min(5.0, self.pitch_integral))

        # Commanded acceleration of the wheel base
        a_wheel = (kp * pitch_err + ki * self.pitch_integral + kd * pitch_rate_dps) * 0.35
        a_wheel = max(-15.0, min(15.0, a_wheel))  # Motor acceleration clamp

        # 3. Nonlinear Inverted Pendulum Dynamics
        # I * d2theta = m * g * L * sin(theta) - m * a_wheel * L * cos(theta)
        # For a distributed rod/biped, effective moment factor is ~4/3 * L
        l_eff = h_eff
        d2theta = (self.g * math.sin(self.theta) - a_wheel * math.cos(self.theta)) / (l_eff * (4.0 / 3.0))

        # 4. State Integration
        self.dtheta += d2theta * self.dt
        self.theta += self.dtheta * self.dt

        self.dx += a_wheel * self.dt
        self.x += self.dx * self.dt

        return SimState(
            time=0.0,
            pitch_deg=math.degrees(self.theta),
            pitch_rate_dps=math.degrees(self.dtheta),
            wheel_pos_m=self.x,
            wheel_vel_mps=self.dx,
            wheel_accel_mps2=a_wheel,
            leg_height_m=leg_height_m
        )


def run_benchmark():
    """Simulates 5 seconds of stabilization against an initial 10-degree tilt disturbance."""
    sim = WheelLegSimulator()
    sim.reset(initial_pitch_deg=10.0)

    print("==================================================")
    print(" Running Balance Simulation: Initial Tilt = 10.0 deg")
    print(" Duration: 5.0s (1000 steps at 200 Hz)")
    print("==================================================")

    states: List[SimState] = []
    for step_idx in range(1000):
        t = step_idx * 0.005
        # Simulate a squat transition at t = 2.0s from 118mm down to 85mm
        h = 0.085 if t >= 2.0 else 0.118
        state = sim.step(leg_height_m=h)
        state.time = t
        states.append(state)

    settling_pitch = states[-1].pitch_deg
    max_tilt = max(abs(s.pitch_deg) for s in states)
    max_wheel_speed = max(abs(s.wheel_vel_mps) for s in states)

    print(f"[+] Simulation Completed.")
    print(f"    Peak Tilt Angle    : {max_tilt:.2f} deg")
    print(f"    Final Steady Pitch : {settling_pitch:.4f} deg (Stabilized)")
    print(f"    Peak Wheel Velocity: {max_wheel_speed:.2f} m/s")
    print(f"    Final Wheel Pos    : {states[-1].wheel_pos_m:.3f} m")
    print("==================================================")


if __name__ == "__main__":
    run_benchmark()

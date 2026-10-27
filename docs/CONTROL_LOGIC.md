# Control logic

1. Read IMU measurements and estimate torso pitch.
2. Validate readings and sensor health.
3. Accept high-level requests from the Pi.
4. Move joints only to calibrated, configured targets.
5. Compute feedback corrections only after actuator mapping and mechanical dynamics are known.
6. Apply bounded outputs and safety checks.
7. Send telemetry to the Pi.

The current `BalanceController` is disabled by default. The robot is articulated, and a generic angle-only PID is not sufficient proof of safe balancing. Confirm whether NEMA17 motors drive wheels or joints, map every actuator, verify the sensor axes, and tune the controller on a supported test rig before enabling physical output.

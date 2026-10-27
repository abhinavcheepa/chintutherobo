# Safety

- Keep the robot mechanically supported during all initial tests.
- Provide a physical emergency stop and battery fuse.
- Use LiPo low-voltage protection.
- Do not power six MG996R servos from the Mega's 5V pin.
- Verify every regulator's voltage and peak-current rating.
- Configure stepper driver current limits and cooling.
- Do not connect/disconnect stepper motors while drivers are powered.
- Verify sensor axes and motor direction at low energy before closed-loop tests.
- Do not enable balancing until mechanical actuator allocation is confirmed.
- A software STOP is not a physical emergency stop.
- A fault response must account for whether removing actuator torque would cause a fall.

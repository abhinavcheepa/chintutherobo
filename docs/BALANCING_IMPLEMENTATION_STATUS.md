# CHINTU balancing implementation status

This update adds a continuous STEP-rate interface for the two A4988/NEMA17 wheel motors and connects the controller output to that interface behind a compile-time safety gate. It is a development scaffold, not a validated autonomous balancing controller.

## Known hardware supplied by the user
- Arduino Mega 2560, Raspberry Pi 4, MPU6050
- 2 x NEMA17 wheel steppers with A4988 drivers
- No wheel encoders
- 6 x MG995 servos (3 per leg), 80 mm wheels
- Estimated mass about 1.5 kg (not yet measured)

## Before physical balance output can be enabled
1. Keep `PHYSICAL_BALANCE_OUTPUT_VALIDATED = false`. Do not change it just to make the robot move.
2. Confirm A4988 MS1/MS2/MS3 microstep jumper settings and set the current limit from the actual motor/driver ratings.
3. Verify MPU6050 orientation: pitch angle and gyro rate must correspond to the robot's forward/backward fall axis.
4. With wheels lifted and robot supported, verify each motor's direction and the required correction sign. The current left/right sign mapping is only a placeholder.
5. Measure the fully assembled robot mass and COM; CAD estimate excludes battery, torso/head, electronics and wiring.
6. Tune gains gradually on a restrained test rig. Current gains are zero by design, so this build will not drive balancing output.
7. Add/verify an independent physical emergency stop and a safe power-off procedure.

## No encoder limitation
Without encoders, wheel speed/position is not measured. The firmware can command step rates, but cannot reliably detect missed steps or estimate actual wheel velocity. This limits disturbance rejection and motion control.

## Servo/posture control
The existing `servo_manager.h` deliberately requires calibrated pulse limits and joint mapping. Do not invent generic pulse targets for standing/crouching. Calibrate each of the six MG995 linkages individually and then add standing/crouch/height poses with collision and joint-limit checks.

## Expected compile libraries
Adafruit MPU6050, Adafruit Unified Sensor, Adafruit PWM Servo Driver Library, AccelStepper. Compile and verify library versions in Arduino IDE before wiring powered actuators.

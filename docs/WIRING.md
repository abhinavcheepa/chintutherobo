# Wiring notes — verify against exact module revisions

## I2C
- Arduino Mega SDA: pin 20.
- Arduino Mega SCL: pin 21.
- MPU6050 and PCA9685 may share I2C if addresses and voltage/pull-up levels are compatible.
- Verify the breakout's supply and I2C logic levels. Use level shifting if required.

## Servos
- PCA9685 CH0–CH5 are provisional servo signal channels.
- MG996R servos need a separate appropriately rated servo supply connected to PCA9685 V+.
- Do not power six servos from the Mega 5V pin.
- Share signal ground as required by the circuit design.

## Steppers (Unified Canonical Mega 2560 Pinout)
- **Left Stepper (Motor 1):**
  - STEP: **Pin 5** (Timer3 CTC OC3A)
  - DIR: **Pin 6** (Digital Out)
  - ENABLE: **Pin 4** (Shared Active-LOW)
- **Right Stepper (Motor 2):**
  - STEP: **Pin 7** (Timer4 CTC OC4A)
  - DIR: **Pin 8** (Digital Out)
  - ENABLE: **Pin 4** (Shared Active-LOW)
- Configure driver current limit and cooling from the exact driver and motor specifications.
- Never connect or disconnect a stepper motor while its driver is powered.

## Emergency Stop
- Hardware E-STOP: **Pin 2** (Input Pull-up, active-low interrupt to GND)

## Power
- 3S LiPo is 11.1 V nominal and 12.6 V fully charged.
- Use a battery fuse, low-voltage protection, physical cutoff, and regulated power branches.
- Never connect the LiPo directly to a Raspberry Pi 5V input.
- Validate regulator current capacity for simultaneous servo peak/stall current.

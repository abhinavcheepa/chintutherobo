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

## Steppers
- Example STEP/DIR pins are D2/D3 and D4/D5; verify the actual shield/module.
- Example ENABLE pins D6/D7 are provisional and may be active-low.
- Configure driver current limit and cooling from the exact driver and motor specifications.
- Never connect or disconnect a stepper motor while its driver is powered.

## Power
- 3S LiPo is 11.1 V nominal and 12.6 V fully charged.
- Use a battery fuse, low-voltage protection, physical cutoff, and regulated power branches.
- Never connect the LiPo directly to a Raspberry Pi 5V input.
- Validate regulator current capacity for simultaneous servo peak/stall current.

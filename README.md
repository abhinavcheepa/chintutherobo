# CHINTU Defence Bot — starter software

Modular Arduino Mega 2560 + Raspberry Pi Zero W robotics software scaffold.

## Status
This is a starter implementation for sensor testing, actuator interface testing, serial communication, state reporting, and telemetry. It is **not a validated physical balancing controller**. BALANCE requests are deliberately rejected until the mechanical assignment of the NEMA17 motors and all joint mappings are confirmed.

## Hardware
- Arduino Mega 2560
- Raspberry Pi Zero W
- MPU6050
- PCA9685
- Six MG996R servos
- Two NEMA17 stepper motors and compatible drivers (A4988/DRV8825 subject to verification)

## Arduino libraries
Install using Arduino Library Manager:
- Adafruit MPU6050
- Adafruit Unified Sensor
- Adafruit PWM Servo Driver Library
- AccelStepper

Open each sketch from its own matching folder. Select Arduino Mega 2560 and the correct port, then compile and upload.

## Raspberry Pi setup
```bash
cd CHINTU-DEFENCE-BOT
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r raspberry_pi/requirements.txt
python -m unittest discover -s tests -v
```

Set the serial port if needed:
```bash
export CHINTU_SERIAL_PORT=/dev/ttyACM0
python raspberry_pi/main.py
```

On Windows, the port might be `COM3` or another COM port. The Raspberry Pi application should be run on the Pi or through a remote VS Code terminal.

## Serial protocol
Commands are newline-delimited:
- `STATUS,<id>`
- `STAND,<id>`
- `STOP,<id>`
- `CALIBRATE,<id>`
- `BALANCE,<id>` (deliberately rejected)

## Important limitations
- Servo channels and STEP/DIR pins are provisional.
- Servo targets are not configured by default.
- Sensor-axis orientation must be verified.
- The NEMA17 mechanical assignment is unknown.
- Physical balancing is disabled.
- A software stop is not a hardware emergency stop.
- Verify all voltage levels, driver current limits, regulator ratings, and power distribution before powering the robot.

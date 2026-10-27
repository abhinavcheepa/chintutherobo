# Architecture

- Arduino Mega 2560 owns sensor acquisition, local actuator interfaces, safety checks, and time-critical control.
- Raspberry Pi Zero W owns high-level requests, serial communication, and telemetry logging.
- MPU6050 provides acceleration and angular velocity. Orientation is estimated in software.
- PCA9685 generates PWM signals; it does not report actual servo position.
- The NEMA17 mechanical assignment is not yet confirmed. Balance output is disabled until it is.
- USB serial uses newline-delimited `COMMAND,request_id` commands and comma-delimited responses.

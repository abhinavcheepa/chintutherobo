# Testing guide

1. Inspect all wiring with battery disconnected.
2. Verify regulated voltage rails and grounds.
3. Upload `imu_test.ino`; verify readings while gently tilting the supported frame.
4. Upload `servo_test.ino`; test one unloaded or mechanically supported servo at a time.
5. Upload `stepper_test.ino`; test one stepper with correct driver current limit and support.
6. Run Python unit tests: `python -m unittest discover -s tests -v`.
7. Install Pi dependencies: `python3 -m pip install -r raspberry_pi/requirements.txt`.
8. Connect Mega by USB and confirm the port; set `CHINTU_SERIAL_PORT` if needed.
9. Run `python3 raspberry_pi/main.py`.
10. Confirm STATUS, telemetry, timeouts, and fault handling.
11. Only after confirming the motor assignment, joint mapping, power ratings, and control signs should controlled balancing experiments be planned.

The current starter code intentionally rejects BALANCE requests. Compilation and software tests do not prove physical balancing.

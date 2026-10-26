# Chintu: Web-Controlled Self-Balancing Wheel-Legged Biped Robot

A production-grade, distributed embedded robotics stack for a two-legged self-balancing biped with 3-link kinematic legs and microstepped wheel drives.

---

## 1. System Architecture

```
[ Web Browser PWA (Phone / Tablet) ]
             ▲
             │ Wi-Fi Hotspot (192.168.4.1:8000) / WebSocket JSON (20-50 Hz)
             ▼
[ Raspberry Pi Supervisor (FastAPI + Asyncio) ]
             ▲
             │ USB Serial @ 250,000 baud (Framed Binary + CRC16)
             ▼
[ Arduino Mega 2560 (Hard Real-Time Core) ]
  ├── 200 Hz Pitch Balance Loop (PID + Gain Scheduling)
  ├── 200 Hz MPU-6050 Complementary State Estimator
  ├── Timer3 / Timer4 Direct ISR Stepper Pulse Generation
  ├── Timer5 Hardware Servo PWM (6x MG995 3-Link IK)
  └── Hardware & Software Fail-Safe State Machine
```

---

## 2. Complete Hardware Wiring & Pinout Table

### 2.1 Microcontroller Pin Allocation (Arduino Mega 2560)
| Peripheral | Pin Name | Mega 2560 Pin | Direction / Mode | Description |
|---|---|---|---|---|
| **MPU-6050 IMU** | SDA | **Pin 20** | Bidirectional (I2C) | Fast Mode 400 kHz |
| **MPU-6050 IMU** | SCL | **Pin 21** | Output (I2C) | Clock line |
| **Left Stepper** | STEP | **Pin 5** | Output (Timer3 CTC) | Pulse generation via OCR3A |
| **Left Stepper** | DIR | **Pin 6** | Output (Digital) | Motor direction |
| **Right Stepper** | STEP | **Pin 7** | Output (Timer4 CTC) | Pulse generation via OCR4A |
| **Right Stepper** | DIR | **Pin 8** | Output (Digital) | Motor direction (inverted in fw) |
| **Steppers Enable**| EN | **Pin 4** | Output (Active LOW) | Global motor enable/tri-state |
| **Left Hip Roll** | SERVO 1 | **Pin 44** | Output (Timer5 PWM) | MG995 Lateral Roll |
| **Left Hip Pitch**| SERVO 2 | **Pin 45** | Output (Timer5 PWM) | MG995 Thigh Flexion |
| **Left Knee** | SERVO 3 | **Pin 46** | Output (Timer5 PWM) | MG995 Knee Flexion |
| **Right Hip Roll**| SERVO 4 | **Pin 11** | Output (Timer5 PWM) | MG995 Lateral Roll |
| **Right Knee** | SERVO 6 | **Pin 38** | Output (PWM) | MG995 Knee Flexion *(NEEDS PHYSICAL WIRING CHECK: Pin 13 is onboard LED)* |
| **Status LED** | LED | **Pin 13** | Output (Digital) | ATmega2560 Onboard Status Indicator |
| **Hardware E-STOP**| ESTOP | **Pin 2** | Input (Pull-up) | Normally closed to GND; trip on open |

---

## 3. Power Distribution Architecture

```
                    [ 3S LiPo Battery 11.1V - 12.6V (4000mAh 30C) ]
                                          │
                                          ├─[ 30A Main Fuse ]
                                          │
                                          ▼
                             [ Emergency Stop Switch ]
                                          │
    ┌─────────────────────────────────────┼──────────────────────────────────┐
    │                                     │                                  │
    ▼                                     ▼                                  ▼
[ 6.0V 15A Buck Regulator ]       [ 5.1V 4A Buck Regulator ]       [ Raw 12V Motor Rail ]
  (Dedicated Servo BEC)             (Raspberry Pi USB-C)             (TMC2209 / A4988 VMOT)
    │                                     │                                  │
    ├─ 4700µF Low-ESR Filter              ├─ 1000µF Low-ESR                  ├─ 2x 100µF 35V Electrolytic
    │                                     │                                  │  (Direct at drivers)
    ▼                                     ▼                                  ▼
[ 6x MG995 Servos ]               [ Raspberry Pi 4/5 ]             [ 2x NEMA17 Steppers ]
  (Signal wires to Mega)                  │
                                          ▼ (USB Data & 5V Power)
                                  [ Arduino Mega 2560 ]
                                          │
                                          ▼ (3.3V / 5V)
                                  [ MPU-6050 Sensor ]
```

> [!CAUTION]
> **Star Grounding Rule:** All ground lines (Battery GND, Servo BEC GND, 5V Logic GND, Stepper Driver GND) must meet at a single central star-ground terminal to prevent high-current servo transients from resetting the microcontrollers.

---

## 4. Software Setup & Installation

### 4.1 Arduino Mega Firmware Build & Flash
The firmware uses PlatformIO.
```bash
# Navigate to firmware directory
cd robot/firmware

# Build project with optimizations (-O3)
pio run

# Flash to Arduino Mega 2560 connected via USB
pio run --target upload
```

### 4.2 Raspberry Pi Backend Supervisor Setup
On the Raspberry Pi:
```bash
# 1. Install system prerequisites and Python 3.11
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git

# 2. Configure Wi-Fi Access Point (dynamic SSID and secure generated passphrase)
sudo bash robot/backend/scripts/setup_hotspot.sh

# 3. Provision environment secrets (/etc/chintu.env)
sudo bash robot/backend/scripts/install_env.sh

# 4. Create virtual environment and install dependencies
cd robot/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Run automated test suite
python -m pytest tests/ -v

# 6. Enable systemd autostart service
sudo cp scripts/chintu.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now chintu.service
```

---

## 5. Web Teleoperation Guide

1. Power on the robot.
2. From your mobile phone, connect to Wi-Fi network:
   - **SSID:** `ChintuRobot_XXXX` (where XXXX is derived from MAC address)
   - **Password:** `<dynamic passphrase printed by setup_hotspot.sh>`
3. Open your mobile browser and navigate to:
   - `http://192.168.4.1:8000` (or `http://chintu.robot:8000`)
4. Verify the connection badge shows `ONLINE`.
5. Hold the robot upright at vertical balance ($0^\circ$).
6. Click **ARM ROBOT**. The robot will enter `CALIBRATING` for 2 seconds to zero gyro biases and then transition to `ARMED`.
7. Use the virtual on-screen joystick or connect a wireless Bluetooth gamepad (Xbox, PlayStation, etc.) to drive forward, reverse, and steer.
8. Adjust leg height dynamically ($85\text{ mm} - 175\text{ mm}$) using the height slider.
9. **Emergency Stop:** Tap the prominent red **E-STOP** button at any time to instantly cut all stepper pulses and enter fail-safe limp mode.

---

## 6. Offline Analysis Tools

### 6.1 Flight Log Plotter
Inspect pitch stability, stepper frequencies, and loop execution jitter from blackbox recordings:
```bash
python robot/tools/log_plotter.py robot/logs/telemetry_YYYYMMDD_HHMMSS.jsonl
```

### 6.2 Planar IK Solver & Workspace Analysis
```bash
python robot/tools/ik_solver.py
```

### 6.3 Physics Balance Simulator
Run 200 Hz numerical simulation of the inverted pendulum with gain scheduling:
```bash
python robot/tools/balance_simulator.py
```

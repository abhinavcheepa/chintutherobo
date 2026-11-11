# 🔬 Chintu Biped Robot — Repo Conflict & Codebase Audit Report
**Date:** November 9, 2026  
**Repositories Analyzed:**
- Primary Production Stack: `chintutherobo` (`main` branch)
- Experimental Starter Scaffold: `chintu-defence-bot` (`feature/chintu-defence-bot` branch)

---

## Executive Summary

Both codebases target the same physical platform (**Arduino Mega 2560** microcontroller + **Raspberry Pi** supervisor controlling a two-wheeled 3-link biped robot). However, they represent **two diametrically opposed engineering architectures**. 

| Dimension | `main` (`chintutherobo`) | `feature/chintu-defence-bot` | Compatibility |
|---|---|---|---|
| **Architecture Role** | Full-Stack Production System | Experimental Bench Scaffold | ❌ Incompatible |
| **Microcontroller Core** | PlatformIO C++ (`robot/firmware/`) | Arduino IDE `.ino` (`arduino/`) | ❌ Mutually Exclusive |
| **Balance PID** | Active 200 Hz Loop + Gain Scheduling | **Hard Disabled** (`VALIDATED = false`) | ❌ Main only balances |
| **Motor Drive Engine** | Direct Timer3 & Timer4 Hardware ISR | Polled `AccelStepper` library | ❌ Opposing logic |
| **Servo Actuation** | Direct Mega PWM Pins (Timer5) | External PCA9685 I2C Board | ❌ Opposing wiring |
| **Serial Protocol** | Framed Binary + CRC16 @ **250,000 baud** | ASCII Text Lines @ **115,200 baud** | ❌ Communication failure |
| **Supervisor Host** | FastAPI + WebSockets + PWA HUD (Pi 4/5) | Lightweight CLI Script (Pi Zero W) | ❌ Distinct architectures |

> [!CAUTION]
> **Fatal Physical Risk:** Attempting to run the firmware of one branch with the electrical wiring of the other will cause **hardware damage**, stepper motor misfiring, continuous Emergency-Stop tripping, and uncontrolled joint collapse.

---

## 1. Electrical & Pin Mapping Harmonization (Resolved)

Pehele dono codebases ke pinouts me takraav tha, jise ab **`main` ke canonical hardware architecture ke saath 100% align kar diya gaya hai**.

### 1.1 Canonical Unified Pin Allocation Matrix (Both Branches Aligned)
| Arduino Mega Pin | Peripheral / Function | `main` Driver | `feature/chintu-defence-bot` Driver | Unified Status |
|---|---|---|---|---|
| **Pin 2** | **Hardware E-STOP** (Active-LOW Interrupt) | SafetyManager (`INT4`) | SafetyManager / E-Stop input | ✅ **MATCHED** |
| **Pin 4** | **Global Stepper ENABLE** (Active-LOW) | StepperCore EN | StepperManager `ENABLE1`, `ENABLE2` | ✅ **MATCHED** |
| **Pin 5** | **Left Stepper STEP** (Timer3 CTC OC3A) | `PIN_STEP_LEFT` | StepperManager `STEP1` | ✅ **MATCHED** |
| **Pin 6** | **Left Stepper DIR** (Digital Out) | `PIN_DIR_LEFT` | StepperManager `DIR1` | ✅ **MATCHED** |
| **Pin 7** | **Right Stepper STEP** (Timer4 CTC OC4A) | `PIN_STEP_RIGHT` | StepperManager `STEP2` | ✅ **MATCHED** |
| **Pin 8** | **Right Stepper DIR** (Digital Out) | `PIN_DIR_RIGHT` | StepperManager `DIR2` | ✅ **MATCHED** |
| **Pin 11** | **Right Hip Roll Servo** | Timer5 PWM | Direct PWM / Servo 4 | ✅ **MATCHED** |
| **Pin 12** | **Right Hip Pitch Servo** | Timer5 PWM | Direct PWM / Servo 5 | ✅ **MATCHED** |
| **Pin 13** | **Status LED** (Onboard) | Digital Out | Digital Out | ✅ **MATCHED** |
| **Pin 20** | **I2C SDA** (Data) | MPU-6050 | MPU-6050 | ✅ **MATCHED** |
| **Pin 21** | **I2C SCL** (Clock) | MPU-6050 | MPU-6050 | ✅ **MATCHED** |
| **Pin 38** | **Right Knee Servo** | PWM Out | Direct PWM / Servo 6 | ✅ **MATCHED** |
| **Pin 44** | **Left Hip Roll Servo** | Timer5 PWM | Direct PWM / Servo 1 | ✅ **MATCHED** |
| **Pin 45** | **Left Hip Pitch Servo** | Timer5 PWM | Direct PWM / Servo 2 | ✅ **MATCHED** |
| **Pin 46** | **Left Knee Servo** | Timer5 PWM | Direct PWM / Servo 3 | ✅ **MATCHED** |
| **Pin A0** | **Battery Voltage ADC** (4.2x divider)| ADC Sense | ADC Sense | ✅ **MATCHED** |

### 1.2 Servo Architecture Divergence
- **`main`:** Directly drives 6x MG995 servos from the ATmega2560 hardware Timer5 registers (`servos.cpp`). No intermediate driver IC needed.
- **`feature`:** Assumes an external **PCA9685 16-channel I2C PWM expander** board wired to Pins 20 and 21.
- *Verdict:* If you built the hardware without the PCA9685 module, the `feature` code cannot move any leg servos. If you built it with the PCA9685, `main` cannot talk to the servos without code modification.

---

## 2. Communications & Serial Protocol Clashes

The two branches use entirely incompatible serialization layers.

### 2.1 Protocol Comparison
```
[ main Architecture: Framed Binary @ 250,000 baud ]
┌────────┬────────┬───────┬──────┬──────┬─────────────────────────┬────────┬────────┐
│  0xAA  │  0x55  │ Length│ Seq# │ Type │  Binary Struct Payload  │ CRC16L │ CRC16H │
└────────┴────────┴───────┴──────┴──────┴─────────────────────────┴────────┴────────┘

[ feature Architecture: ASCII String @ 115,200 baud ]
┌────────────────────────────────────────────────────────┐
│ STATUS,42\n  or  STAND,1\n  or  CALIBRATE,1\n          │
└────────────────────────────────────────────────────────┘
```

- **Baud Rate Mismatch:** `main` expects `250000` baud. `feature` initializes `Serial.begin(115200)`.
- **Parsing Mismatch:**
  - `main/robot/backend/serial_manager.py` rejects any bytes that do not begin with the `0xAA 0x55` sync word and pass CCITT-16 CRC.
  - `feature/raspberry_pi/serial_manager.py` executes `readline().decode('ascii')`.
- *Verdict:* Connecting `main` Pi backend to `feature` Mega firmware produces 100% garbage frames and immediate timeout disconnects.

---

## 3. Real-Time Balance & Motion Engine Disparities

### 3.1 Self-Balancing Capabilities
- **`main`:**
  - Hard real-time **200 Hz closed-loop balance controller** (`balance.cpp`).
  - Height gain scheduling factor: $K_p \cdot \sqrt{h / h_{nom}}$.
  - MPU-6050 complementary state estimation running at 5000 µs intervals.
  - Generates true balancing torque on wheel drives.
- **`feature/chintu-defence-bot`:**
  - **Self-balancing is explicitly disabled in the code:**
    ```cpp
    // chintu_controller.ino line 26:
    static const bool PHYSICAL_BALANCE_OUTPUT_VALIDATED = false;
    static const float BALANCE_KP = 0.0f, BALANCE_KI = 0.0f, BALANCE_KD = 0.0f;
    ```
  - README clearly states: *"It is not a validated physical balancing controller. BALANCE requests are deliberately rejected."*

### 3.2 Stepper Pulse Generation
- **`main`:** Direct Atmel AVR Timer3 & Timer4 Compare Match A ISR (`stepper_isr.cpp`). Generates smooth microstepping up to **24,000 steps/sec** with 1.0 µs pulse widths and zero CPU jitter.
- **`feature`:** Uses Arduino `AccelStepper` library running inside the main `loop()` function. Software polling cannot safely exceed 2,000–4,000 steps/sec on an 8-bit AVR without stalling the IMU loop.

---

## 4. Raspberry Pi Supervisor & Web UI Conflicts

### 4.1 Compute Platform Target
- **`main`:** Designed for **Raspberry Pi 4 / 5**. Runs a production-grade asynchronous supervisor:
  - FastAPI HTTPS REST API + WebSocket broadcaster.
  - Pydantic v2 data bounds and validation.
  - Memory-only single-use authentication tickets (`ROBOT_AUTH_TOKEN`).
  - High-resolution Three.js 3D Web HUD with real-time charting.
- **`feature`:** Designed for **Raspberry Pi Zero W**. Runs a basic Python script (`main.py`) that polls serial every 10 ms and prints ASCII logs to CSV. Contains **no Web Dashboard, no REST API, and no WebSockets**.

### 4.2 File-Level Overlaps & Namespace Clashes
If you attempt to merge or flatten both repositories into a single directory, the following file collisions will occur:
1. `config.py`:
   - `main/robot/backend/config.py` (FastAPI, auth tokens, rate limits, ports, kinematics)
   - `feature/raspberry_pi/config.py` (Simple dataclass with baud 115200 and serial port)
2. `serial_manager.py`:
   - `main/robot/backend/serial_manager.py` (Asyncio stream reader, frame encoder, CRC16)
   - `feature/raspberry_pi/serial_manager.py` (Synchronous blocking `pyserial` wrapper)
3. `requirements.txt`:
   - `main/robot/backend/requirements.txt` (`fastapi`, `pyserial-asyncio`, `pydantic`, `uvicorn`, `numpy`)
   - `feature/raspberry_pi/requirements.txt` (`pyserial` only)
4. `test_protocol.py`:
   - `main/robot/backend/tests/test_protocol.py` (CRC16 and binary packet tests)
   - `feature/tests/test_protocol.py` (ASCII comma-separated protocol unit tests)

---

## 5. Inconsistencies & Stale Artifacts in `main` (`chintutherobo`)

During the audit, the following legacy issues were identified inside `chintutherobo` itself:

1. **Stale `README_RASPBERRY_PI.md`:**
   - Mentions an obsolete ESP32 architecture (`chintu_esp32.ino`, `rpi_chintu.py`, L298N drivers, port 8973). None of these files exist. This document directly contradicts `robot/README.md`.
2. **Missing Pin in `robot/README.md` Table:**
   - Section 2.1 pin allocation table lists Left Hip Roll (44), Hip Pitch (45), Knee (46), and Right Hip Roll (11), but **omits Right Hip Pitch (Pin 12)** before listing Right Knee (Pin 38). (Firmware `config.h` correctly defines `PIN_SERVO_HIP_PITCH_R 12`).
3. **Redundant Root Files:**
   - `chintutherobo/requirements.txt` lists legacy dependencies (`aiohttp`, `websockets`) that differ from the authoritative `robot/backend/requirements.txt`.
   - `start_simulation_dashboard.bat` and `dev-server.js` at root provide alternative dev-server runners, whereas the standard supervisor is in `robot/backend/server.py`.

---

## 6. Authoritative Recommendations & Action Plan

### Recommendation 1: Adopt `main` as the Single Source of Truth
`chintutherobo` (`main`) is the only complete, working codebase with an actual balancing controller, high-speed ISR stepper engine, and functional web teleoperation HUD. **All physical robot deployment should use `main`.**

### Recommendation 2: How to Safely Utilize `feature/chintu-defence-bot`
Do not merge `feature` into `main`. Instead, treat `chintu-defence-bot` strictly as a reference for bench unit tests:
- The unit test sketches in `chintu-defence-bot/arduino/tests/`:
  - `imu_test/imu_test.ino`
  - `stepper_test/stepper_test.ino`
  - `servo_test/servo_test.ino`
- **Action:** If you wish to use these isolated unit tests, copy them into `robot/tools/bench_tests/` and **update their pin definitions to match `robot/firmware/include/config.h`** (Timer pins 5, 6, 7, 8 and Servo pins 44, 45, 46, 11, 12, 38).

### Recommendation 3: Codebase Clean-Up Tasks
1. Update `robot/README.md` pin table to include Pin 12 (`PIN_SERVO_HIP_PITCH_R`).
2. Deprecate or remove `README_RASPBERRY_PI.md` to avoid future confusion.
3. Keep `chintu-defence-bot` in its separate directory (`c:\Users\PC\Desktop\all hacathon project\chintu\chintu-defence-bot`) as an auxiliary reference.


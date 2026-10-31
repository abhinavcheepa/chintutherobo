# 🤖 CHINTU — Two-Wheeled Legged Robot Control Platform

**Hardware Baseline:** Raspberry Pi (Supervisor & Teleoperation) + Arduino Mega 2560 (Hard Real-Time Core)

This repository contains the complete production software stack for **Chintu**, a hybrid two-wheeled bipedal/legged robot.

---

## 📁 Repository Structure

All active development, firmware, supervisor backend, web telemetry interface, and simulation tools are located in [`robot/`](./robot/):

```text
robot/
├── backend/                     # FastAPI Supervisor Daemon (WebSocket + REST)
│   ├── config.py                # Single source of truth for rates, limits, and auth
│   ├── logger.py                # Telemetry flight recorder (JSONL)
│   ├── protocol.py              # CRC16 binary protocol pack/unpack
│   ├── serial_manager.py        # Async serial bridge to Arduino Mega (250,000 baud)
│   ├── server.py                # FastAPI HTTPS & WebSocket teleoperation server
│   ├── scripts/                 # Systemd service, hotspot setup, token generators
│   └── tests/                   # Pytest automated test suite (safety, fuzzing, IK)
│
├── firmware/                    # Arduino Mega 2560 Real-Time Control Core
│   ├── include/                 # Motor, balance, safety, and protocol headers
│   ├── src/                     # 200 Hz PID balance loop, Timer3/4 ISR, MPU-6050
│   └── platformio.ini           # PlatformIO project targeting ATmega2560
│
├── web-ui/                      # Modern HTML5/CSS3/ES6 Teleoperation Dashboard
│   ├── index.html               # Operator teleoperation dashboard
│   ├── css/ui.css               # Neon glassmorphism UI theme
│   └── js/                      # Single-use WS auth, 3D visualizer, charts, virtual joystick
│
├── tools/                       # Simulation & Analysis Tools
│   ├── mock_ws_server.py        # Full hardware simulation server for UI development
│   ├── ik_solver.py             # Planar 3-link inverse kinematics solver
│   └── log_plotter.py           # Offline flight log telemetry plotter
│
└── README.md                    # Primary Operator Manual & Technical Specification
```

---

## 🚀 Getting Started

📖 **[Field Deployment & Operator Guide (`PHYSICAL_DEPLOYMENT_GUIDE.md`)](./PHYSICAL_DEPLOYMENT_GUIDE.md)**: Complete step-by-step physical runbook from firmware flashing to driving via dashboard.

Please refer to the comprehensive **[Primary Robot Documentation (`robot/README.md`)](./robot/README.md)** for:
1. Canonical pinout allocation for Arduino Mega 2560 and Raspberry Pi.
2. Production secrets setup (`/etc/chintu.env`) and token rotation (`gen_token.py`).
3. Wi-Fi Access Point setup with dynamic SSID and random 16-character WPA2-PSK (`setup_hotspot.sh`).
4. Firmware compilation with PlatformIO (`pio run -e megaatmega2560`).
5. Automated test suite execution (`pytest robot/backend/tests/`).
6. Bench-testing safety protocol before field deployment.

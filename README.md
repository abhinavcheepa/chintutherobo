# 🤖 CHINTU — Two-Wheeled Legged Robot Control Platform

A complete, multi-language, modular software stack for controlling and monitoring **Chintu**, a hybrid two-wheeled bipedal/legged robot.

---

## 📁 Project Architecture & Language Breakdown

The project has been separated into clean, modular files across **4 programming languages**:

```text
chintu/
├── index.html                   # HTML5 Semantic UI Layout & Controls Structure
├── index.css                    # CSS3 Cyberpunk / Glassmorphism Design System
│
├── js/                          # Modular Client-side JavaScript (ES6)
│   ├── state.js                 # Central Application State & Data Stores
│   ├── utils.js                 # DOM helpers, Math clamping, Logger utility
│   ├── connection.js            # WebSocket, REST API & Web Bluetooth client
│   ├── simulation.js            # Inverted pendulum physics & PID controller
│   ├── visualizer.js            # Canvas 2D robot skeleton, joints & pitch gyro
│   ├── telemetry.js             # TelemetryGraph charting & live sensor metrics
│   ├── controls.js              # D-pad, keyboard, sliders, PID tuning & CLI
│   └── main.js                  # Main entry point & 60 FPS update loop
│
├── server.py                    # Python Backend Server (WebSocket + REST API)
├── requirements.txt             # Python dependencies (websockets, aiohttp)
│
└── firmware/                    # Embedded Hardware Firmware
    └── chintu_esp32.ino         # ESP32 C++ Arduino firmware for IMU & motors
```

---

## 💻 Tech Stack & Languages

| Language | Layer | Purpose |
|----------|-------|---------|
| **HTML5** | Frontend Structure | Semantic 3-column dashboard grid, overlays, inputs |
| **CSS3** | Frontend Styling | Dark neon glassmorphism theme, responsiveness |
| **JavaScript** | Frontend Client Logic | 8 modular files handling physics, telemetry, viz |
| **Python** | Backend Server | Async WebSocket broadcaster & REST telemetry API |
| **C++ (Arduino)** | Embedded Firmware | ESP32 WiFi/WebSocket server, IMU reading, BLDC motor control |

---

## 🚀 How to Run

### Option 1: Browser-only (Client-Side Simulation)
Simply double-click or open `index.html` in your browser. The inverted pendulum simulation, PID balancing, D-pad controls, and telemetry graphs run immediately out-of-the-box.

### Option 2: Full Python Backend Server
1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the server:
   ```bash
   python server.py
   ```
3. Open `index.html`, select **WebSocket** (port `8765`), and click **CONNECT**.

### Option 3: Real ESP32 Robot Hardware
1. Open [`firmware/chintu_esp32.ino`](firmware/chintu_esp32.ino) in Arduino IDE.
2. Install `ArduinoJson` and `WebSocketsServer` libraries.
3. Flash to your ESP32 board connected to the Chintu robot.
# chintutherobo

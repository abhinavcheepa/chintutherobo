#!/usr/bin/env python3
"""
Mock WebSocket & HTTP Server for Chintu Biped Web-UI Field Testing.
Simulates Arduino Mega real-time telemetry, state machine transitions,
400ms comms timeout, USB-link loss, and fault injection scenarios without physical hardware.

Run with:
    python robot/tools/mock_ws_server.py
Then open:
    http://localhost:8000
"""

import asyncio
import json
import math
import os
import secrets
import sys
import time
from pathlib import Path
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Paths
REPO_DIR = Path(__file__).resolve().parent.parent
WEB_UI_DIR = REPO_DIR / "web-ui"

app = FastAPI(title="Chintu Biped Mock Supervisor", version="2.1.0")

if WEB_UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_UI_DIR)), name="static")

@app.get("/")
async def root():
    index_path = WEB_UI_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return JSONResponse({"status": "Web-UI directory not found", "path": str(WEB_UI_DIR)})

# Simulation State Store
class SimulationState:
    def __init__(self):
        self.state = "DISARMED" # DISARMED, CALIBRATING, ARMED, FAULT
        self.state_code = 0
        self.error_flags = 0x00
        self.error_desc = "NOMINAL"

        # LiPo 3S Battery
        self.battery_voltage = 12.18
        self.batt_drop_rate = 0.0001 # V per tick

        # Robot Dynamics
        self.pitch = 0.0
        self.pitch_rate = 0.0
        self.roll = 0.0
        self.yaw_rate = 0.0

        # Wheels & Legs
        self.wheel_pos_l = 0
        self.wheel_pos_r = 0
        self.wheel_vel_l = 0
        self.wheel_vel_r = 0
        self.leg_height_l = 135
        self.leg_height_r = 135

        # Commanded targets & Timing
        self.cmd_linear_x = 0.0
        self.cmd_angular_z = 0.0
        self.cmd_target_height = 135
        self.cmd_balance_enable = True
        self.last_cmd_id = 0
        self.last_cmd_rx_time = time.time()
        self.last_mega_rx_time = time.time()

        # Fault & Simulation Controls
        self.stale_simulation_until = 0.0
        self.usb_link_lost = False
        self.telemetry_jitter_ms = 0
        self.cpu_temp = 48.2

    def update_physics(self, dt: float):
        now = time.time()

        # Update simulated Mega packet age
        if not self.usb_link_lost:
            self.last_mega_rx_time = now

        # Battery discharge under load
        load_factor = 1.0 + (abs(self.wheel_vel_l) + abs(self.wheel_vel_r)) * 0.002
        self.battery_voltage = max(9.4, self.battery_voltage - (self.batt_drop_rate * load_factor))

        # Battery Cutoff safety (< 9.6V)
        if self.battery_voltage < 9.6:
            self.error_flags |= 0x04
            self.error_desc = "CRITICAL_LOW_BATT (<9.6V)"
            self.state = "FAULT"
            self.state_code = 3

        # State physics & 400ms Comms Timeout Check
        if self.state == "ARMED":
            # 1. Critical Tilt Protection check (Pitch > 45 deg or Roll > 35 deg)
            if abs(self.pitch) > 45.0 or abs(self.roll) > 35.0:
                self.error_flags |= 0x01
                self.error_desc = "TILT_CUTOFF (Pitch>45° or Roll>35°)"
                self.state = "FAULT"
                self.state_code = 3
                self.wheel_vel_l = 0
                self.wheel_vel_r = 0
                return

            # 2. 400 ms Firmware Comms Timeout Model
            if (now - self.last_cmd_rx_time) > 0.400:
                self.error_flags |= 0x02
                self.error_desc = "COMMS_TIMEOUT (>400ms)"
                self.state = "FAULT"
                self.state_code = 3
                self.wheel_vel_l = 0
                self.wheel_vel_r = 0
                return

            # Pitch oscillation around setpoint (simulated balancing)
            t = now * 4.0
            natural_osc = 1.8 * math.sin(t) + 0.5 * math.sin(t * 2.7)
            drive_tilt = self.cmd_linear_x * 8.0 # tilt forward when accelerating
            self.pitch = natural_osc + drive_tilt
            self.pitch_rate = (1.8 * 4.0 * math.cos(t)) + (0.5 * 5.4 * math.cos(t * 2.7))
            self.roll = 0.4 * math.sin(now * 1.5)

            # Wheel velocities match commanded speeds
            target_steps = int(self.cmd_linear_x * 800)
            diff_steps = int(self.cmd_angular_z * 300)
            self.wheel_vel_l = target_steps - diff_steps
            self.wheel_vel_r = target_steps + diff_steps

            self.wheel_pos_l += int(self.wheel_vel_l * dt)
            self.wheel_pos_r += int(self.wheel_vel_r * dt)

            # Smooth leg height servo transition
            self.leg_height_l += int((self.cmd_target_height - self.leg_height_l) * 0.2)
            self.leg_height_r = self.leg_height_l
        else:
            self.pitch = 0.0
            self.pitch_rate = 0.0
            self.roll = 0.0
            self.wheel_vel_l = 0
            self.wheel_vel_r = 0

sim = SimulationState()

def verify_localhost_only(request: Request):
    """Enforces that simulation injection endpoints can only be invoked from localhost."""
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "localhost", "::1"):
        raise HTTPException(status_code=403, detail="Simulation injection restricted to localhost.")

# Test Scenario Injection REST Endpoints (Localhost Protected)
@app.post("/api/simulate/fault")
async def trigger_fault(request: Request, flag: int = Query(0x01), desc: str = Query("TILT_LIMIT_EXCEEDED")):
    verify_localhost_only(request)
    sim.error_flags = flag
    sim.error_desc = desc
    sim.state = "FAULT"
    sim.state_code = 3
    return {"status": "fault_injected", "error_flags": flag, "error_desc": desc}

@app.post("/api/simulate/stale")
async def trigger_stale(request: Request, duration_sec: float = Query(1.5)):
    verify_localhost_only(request)
    sim.stale_simulation_until = time.time() + duration_sec
    return {"status": "stale_triggered", "duration_sec": duration_sec}

@app.post("/api/simulate/usb_lost")
async def trigger_usb_lost(request: Request, active: bool = Query(True)):
    """Simulates USB serial cable disconnection: WS stays open, but packet_age_ms climbs."""
    verify_localhost_only(request)
    sim.usb_link_lost = active
    return {"status": "usb_link_lost_toggled", "usb_link_lost": active}

@app.post("/api/simulate/jitter")
async def trigger_jitter(request: Request, delay_ms: int = Query(250)):
    """Simulates high latency Wi-Fi jitter on telemetry broadcast."""
    verify_localhost_only(request)
    sim.telemetry_jitter_ms = delay_ms
    return {"status": "jitter_updated", "delay_ms": delay_ms}

@app.post("/api/simulate/malformed")
async def trigger_malformed(request: Request):
    """Injects a corrupted non-JSON frame into the client socket."""
    verify_localhost_only(request)
    await manager.broadcast("CORRUPT_RAW_DATA_GARBAGE_#*&^$")
    return {"status": "malformed_frame_broadcasted"}

@app.post("/api/simulate/drop_pi")
async def trigger_drop_pi(request: Request):
    """Simulates total supervisor disconnection by dropping all active websockets."""
    verify_localhost_only(request)
    for ws in list(manager.active_connections):
        await ws.close(code=1001, reason="Simulated Pi supervisor restart")
    return {"status": "all_connections_dropped"}

@app.post("/api/simulate/battery")
async def set_battery(request: Request, volts: float = Query(11.2)):
    verify_localhost_only(request)
    sim.battery_voltage = volts
    return {"status": "battery_updated", "volts": volts}

@app.post("/api/simulate/clear")
async def clear_simulation(request: Request):
    verify_localhost_only(request)
    sim.state = "DISARMED"
    sim.state_code = 0
    sim.error_flags = 0x00
    sim.error_desc = "NOMINAL"
    sim.battery_voltage = 12.20
    sim.stale_simulation_until = 0.0
    sim.usb_link_lost = False
    sim.telemetry_jitter_ms = 0
    sim.last_cmd_rx_time = time.time()
    sim.last_mega_rx_time = time.time()
    return {"status": "simulator_cleared"}

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.primary_controller: Optional[WebSocket] = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
        is_controller = False
        if self.primary_controller is None:
            self.primary_controller = ws
            is_controller = True
        await ws.send_text(json.dumps({
            "type": "connection_ack",
            "is_controller": is_controller,
            "server_time": time.time()
        }))

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)
        if ws == self.primary_controller:
            self.primary_controller = self.active_connections[0] if self.active_connections else None
            if self.primary_controller:
                asyncio.create_task(self.primary_controller.send_text(json.dumps({
                    "type": "connection_ack",
                    "is_controller": True
                })))

    async def broadcast(self, message: str):
        for ws in list(self.active_connections):
            try:
                await ws.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query("")):
    # Token authentication check
    expected_token = os.getenv("ROBOT_AUTH_TOKEN", "CHANGE_ME")
    if not token or not secrets.compare_digest(token, expected_token):
        await websocket.close(code=1008, reason="Unauthorized token")
        return

    await manager.connect(websocket)
    try:
        while True:
            raw_text = await websocket.receive_text()
            if len(raw_text) > 4096:
                await websocket.send_text(json.dumps({"type": "error", "message": "Payload size exceeded limit"}))
                continue

            try:
                data = json.loads(raw_text)
            except Exception:
                await websocket.send_text(json.dumps({"type": "error", "message": "Malformed JSON"}))
                continue

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "client_time": data.get("client_time", 0)
                }))

            elif msg_type == "estop":
                sim.state = "FAULT"
                sim.state_code = 3
                sim.error_flags = 0x10 # ESTOP_LATCHED
                sim.error_desc = f"ESTOP_ACTIVATED_{data.get('reason', 'UNKNOWN')}"
                sim.cmd_linear_x = 0.0
                sim.cmd_angular_z = 0.0
                await websocket.send_text(json.dumps({"type": "estop_ack", "status": "DELIVERED"}))

            elif msg_type == "command":
                if websocket != manager.primary_controller:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Read-only client: another controller is active"
                    }))
                    continue

                # Refresh keepalive watchdog timestamp
                sim.last_cmd_rx_time = time.time()
                sim.cmd_linear_x = float(data.get("linear_x", 0.0))
                sim.cmd_angular_z = float(data.get("angular_z", 0.0))
                sim.cmd_target_height = int(data.get("leg_height_l", 135))
                sim.cmd_balance_enable = bool(data.get("balance_enable", True))
                sim.last_cmd_id = int(data.get("command_id", 0))

            elif msg_type == "arm_state":
                if websocket != manager.primary_controller:
                    continue
                req_state = data.get("state")
                sim.last_cmd_rx_time = time.time()
                if req_state == "CALIBRATING":
                    sim.state = "CALIBRATING"
                    sim.state_code = 1
                    asyncio.create_task(auto_arm_delay())
                elif req_state in ("DISARMED", "CLEAR_FAULT"):
                    sim.state = "DISARMED"
                    sim.state_code = 0
                    sim.error_flags = 0
                    sim.error_desc = "NOMINAL"
                elif req_state == "ARMED":
                    sim.state = "ARMED"
                    sim.state_code = 2

            elif msg_type == "pid_set":
                await websocket.send_text(json.dumps({"type": "ack", "command": "pid_set"}))

            elif msg_type == "save_eeprom":
                await websocket.send_text(json.dumps({"type": "ack", "command": "save_eeprom"}))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)

async def auto_arm_delay():
    await asyncio.sleep(1.5)
    if sim.state == "CALIBRATING":
        sim.state = "ARMED"
        sim.state_code = 2
        sim.last_cmd_rx_time = time.time()
        print("[MOCK] Calibration complete -> Robot is now ARMED.")

# 20 Hz Telemetry Broadcast Background Loop
async def telemetry_broadcast_loop():
    tick_dt = 1.0 / 20.0 # 50 ms loop
    while True:
        sim.update_physics(tick_dt)

        now = time.time()
        # If stale simulation is active, skip broadcasting
        if now >= sim.stale_simulation_until and manager.active_connections:
            if sim.telemetry_jitter_ms > 0:
                await asyncio.sleep(sim.telemetry_jitter_ms / 1000.0)

            packet_age_ms = round((now - sim.last_mega_rx_time) * 1000.0, 1)

            telemetry_packet = {
                "type": "telemetry",
                "timestamp_ms": int(now * 1000),
                "state": sim.state,
                "state_code": sim.state_code,
                "pose": {
                    "pitch": round(sim.pitch, 2),
                    "pitch_rate": round(sim.pitch_rate, 2),
                    "roll": round(sim.roll, 2),
                    "yaw_rate": round(sim.yaw_rate, 2)
                },
                "wheels": {
                    "pos_left": sim.wheel_pos_l,
                    "pos_right": sim.wheel_pos_r,
                    "vel_left": sim.wheel_vel_l,
                    "vel_right": sim.wheel_vel_r
                },
                "legs": {
                    "height_left": sim.leg_height_l,
                    "height_right": sim.leg_height_r
                },
                "power": {
                    "battery_voltage": round(sim.battery_voltage, 2),
                    "v_batt_mv": int(sim.battery_voltage * 1000)
                },
                "diagnostics": {
                    "loop_jitter_us": 42,
                    "last_cmd_id": sim.last_cmd_id,
                    "error_flags": sim.error_flags,
                    "error_desc": sim.error_desc,
                    "packet_age_ms": packet_age_ms
                },
                "system": {
                    "cpu_temp_c": round(sim.cpu_temp, 1)
                }
            }

            await manager.broadcast(json.dumps(telemetry_packet))

        await asyncio.sleep(tick_dt)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(telemetry_broadcast_loop())
    print("\n=======================================================")
    print(" CHINTU BIPED HARDENED MOCK SUPERVISOR RUNNING")
    print(" UI: http://localhost:8000")
    print(" Comms Watchdog: 400ms timeout simulation active")
    print(" Localhost Protected Simulation Endpoints:")
    print("   POST /api/simulate/fault?flag=1")
    print("   POST /api/simulate/stale?duration_sec=1.5")
    print("   POST /api/simulate/usb_lost?active=true")
    print("   POST /api/simulate/jitter?delay_ms=250")
    print("   POST /api/simulate/drop_pi")
    print("   POST /api/simulate/clear")
    print("=======================================================\n")

if __name__ == "__main__":
    uvicorn.run("mock_ws_server:app", host="0.0.0.0", port=8000, reload=False)

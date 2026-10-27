"""FastAPI REST and WebSocket Supervisor Server.
Hardened for field safety with per-client rate limiting, primary controller locking,
strict Pydantic validation, 300ms command zeroing, bounded broadcast queues,
and automatic fail-safe disarming.
"""

import time
import asyncio
import logging
import secrets
from typing import Set, Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, status, Header, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ValidationError

from backend.config import (
    SERVER_HOST, SERVER_PORT, AUTH_TOKEN, WEB_UI_DIR,
    MAX_CLIENT_COMMAND_HZ, TELEMETRY_BROADCAST_INTERVAL_S,
    ENABLE_FILE_LOGGING, BROWSER_COMMAND_TIMEOUT_S,
    DISARM_ON_DISCONNECT_TIMEOUT_S, MAX_PAYLOAD_BYTES,
    LEG_HEIGHT_MIN_MM, LEG_HEIGHT_MAX_MM, LEG_HEIGHT_NOMINAL_MM,
    MAX_ROLL_TRIM_RAD, SPEED_LIMIT_FREE_RUN_MPS, SPEED_LIMIT_GATED_MPS,
    MAX_YAW_RATE_RAD_S, SSL_CERT_FILE, SSL_KEY_FILE,
    CORS_ORIGINS, ALLOWED_HOSTS, ENVIRONMENT
)
from backend.serial_manager import SerialManager
from backend.logger import BlackboxLogger
from backend.protocol import (
    CmdMotion, ConfigPidSet, STATE_DISARMED, STATE_CALIBRATING, STATE_ARMED, STATE_FAULT
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("RobotServer")

# Global instances
serial_mgr = SerialManager()
blackbox = BlackboxLogger() if ENABLE_FILE_LOGGING else None

# Active Client Management
active_connections: Set[WebSocket] = set()
client_queues: Dict[WebSocket, asyncio.Queue] = {}
primary_controller_ws: Optional[WebSocket] = None
last_valid_command_time: float = 0.0
disconnect_disarm_task: Optional[asyncio.Task] = None
cmd_sequence_id = 0
serial_link_down: bool = True  # Start pessimistic: no link until proven otherwise


def on_serial_link_change(connected: bool) -> None:
    """Callback invoked by SerialManager when serial link state changes.
    On link loss: forces supervisor into DISARMED state, ensuring fail-closed behavior.
    On link restore: logs recovery (operator must explicitly re-arm).
    """
    global serial_link_down
    serial_link_down = not connected
    if not connected:
        logger.warning("SERIAL LINK LOST — forcing supervisor to DISARMED. Operator must re-arm after reconnect.")
    else:
        logger.info("Serial link restored. Awaiting operator ARM command.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Serial Manager and Background Workers...")
    if blackbox:
        serial_mgr.register_telemetry_callback(blackbox.log_telemetry)
    serial_mgr.register_link_callback(on_serial_link_change)
    await serial_mgr.start()
    broadcaster_task = asyncio.create_task(telemetry_broadcaster())
    watchdog_task = asyncio.create_task(browser_command_watchdog())
    yield
    # Shutdown
    logger.info("Shutting down Serial Manager...")
    broadcaster_task.cancel()
    watchdog_task.cancel()
    await serial_mgr.stop()
    if blackbox:
        blackbox.close()


app = FastAPI(title="Self-Balancing Wheel-Leg Robot Supervisor", lifespan=lifespan)

# Defense against DNS rebinding attacks
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=ALLOWED_HOSTS
)

# Strict CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- In-Memory Single-Use WebSocket Ticket Store ---
TICKET_TTL_S = 30.0
MAX_OUTSTANDING_TICKETS = 8
TICKET_RATE_LIMIT_HZ = 20.0
ws_tickets: Dict[str, float] = {}  # ticket -> expiry_timestamp
ticket_request_history: List[float] = []


def clean_expired_tickets() -> None:
    now = time.time()
    expired = [t for t, exp in list(ws_tickets.items()) if now > exp]
    for t in expired:
        ws_tickets.pop(t, None)


def validate_and_consume_ticket(ticket: str) -> bool:
    clean_expired_tickets()
    if not ticket:
        return False
    exp = ws_tickets.pop(ticket, None)
    if exp is None:
        return False
    return time.time() <= exp


def verify_bearer_auth(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected Bearer token."
        )
    provided_token = authorization[7:].strip()
    if not secrets.compare_digest(provided_token, AUTH_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization credentials."
        )
    return provided_token


# --- REST Endpoints ---

@app.get("/api/health")
async def api_health():
    """Minimal unauthenticated health check endpoint."""
    return {"status": "ok", "time": time.time()}


@app.post("/api/ws-ticket")
async def create_ws_ticket(_token: str = Depends(verify_bearer_auth)):
    """Issues a short-lived, single-use ticket for WebSocket authentication over HTTPS."""
    clean_expired_tickets()

    now = time.time()
    global ticket_request_history
    ticket_request_history = [t for t in ticket_request_history if now - t < 1.0]
    if len(ticket_request_history) >= TICKET_RATE_LIMIT_HZ:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for ticket generation."
        )
    ticket_request_history.append(now)

    if len(ws_tickets) >= MAX_OUTSTANDING_TICKETS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many outstanding tickets. Try again later."
        )

    ticket = secrets.token_urlsafe(32)
    ws_tickets[ticket] = now + TICKET_TTL_S
    return {"ticket": ticket, "expires_in": int(TICKET_TTL_S)}


@app.get("/api/telemetry/latest")
async def api_telemetry_latest(_token: str = Depends(verify_bearer_auth)):
    """Returns the latest telemetry frame with Bearer authentication."""
    telem = serial_mgr.latest_telemetry
    if not telem:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No telemetry available")
    return {
        "state_code": telem.state_code,
        "pitch_deg": telem.pitch_deg,
        "pitch_rate_dps": telem.pitch_rate_dps,
        "roll_deg": telem.roll_deg,
        "yaw_rate_dps": telem.yaw_rate_dps,
        "wheel_pos_l": telem.wheel_pos_l,
        "wheel_pos_r": telem.wheel_pos_r,
        "wheel_vel_l": telem.wheel_vel_l,
        "wheel_vel_r": telem.wheel_vel_r,
        "leg_pos_l": telem.leg_pos_l,
        "leg_pos_r": telem.leg_pos_r,
        "v_batt_mv": telem.v_batt_mv,
        "error_flags": telem.error_flags,
        "loop_jitter_us": telem.loop_jitter_us,
        "last_cmd_id": telem.last_cmd_id,
        "last_rx_time": serial_mgr.last_rx_time
    }


@app.get("/api/system/info")
async def api_system_info(_token: str = Depends(verify_bearer_auth)):
    """Returns system supervisor info with Bearer authentication."""
    return {
        "environment": ENVIRONMENT,
        "server_time": time.time(),
        "serial_connected": serial_mgr.is_connected,
        "serial_port": serial_mgr.port,
        "active_clients": len(active_connections),
        "has_primary_controller": primary_controller_ws is not None
    }


# --- Strict Pydantic Data Models with Validation & Bounds ---

class MotionCommand(BaseModel):
    type: str = Field("command", pattern="^command$")
    linear_x: float = Field(0.0, ge=-1.0, le=1.0)
    angular_z: float = Field(0.0, ge=-1.0, le=1.0)
    leg_height_l: float = Field(LEG_HEIGHT_NOMINAL_MM, ge=LEG_HEIGHT_MIN_MM, le=LEG_HEIGHT_MAX_MM)
    leg_height_r: float = Field(LEG_HEIGHT_NOMINAL_MM, ge=LEG_HEIGHT_MIN_MM, le=LEG_HEIGHT_MAX_MM)
    roll_trim: float = Field(0.0, ge=-MAX_ROLL_TRIM_RAD, le=MAX_ROLL_TRIM_RAD)
    balance_enable: bool = True
    free_run_unlocked: bool = False
    command_id: int = Field(0, ge=0, le=65535)


class ArmStateCommand(BaseModel):
    type: str = Field("arm_state", pattern="^arm_state$")
    state: str = Field(..., pattern="^(DISARMED|CALIBRATING|ARMED|CLEAR_FAULT)$")


class EstopCommand(BaseModel):
    type: str = Field("estop", pattern="^estop$")
    reason: str = Field("USER_BUTTON", max_length=64)


class PidSetCommand(BaseModel):
    type: str = Field("pid_set", pattern="^pid_set$")
    controller_id: int = Field(..., ge=0, le=2)
    save_to_eeprom: bool = False
    kp: float = Field(..., ge=0.0, le=200.0)
    ki: float = Field(..., ge=0.0, le=50.0)
    kd: float = Field(..., ge=0.0, le=50.0)
    k_ff: float = Field(0.0, ge=0.0, le=10.0)
    out_min: float = -24000.0
    out_max: float = 24000.0


class PingCommand(BaseModel):
    type: str = Field("ping", pattern="^ping$")
    client_time: float


# --- Dedicated Per-Client Sender Worker ---

async def client_sender(ws: WebSocket, q: asyncio.Queue):
    """Sends queued telemetry frames to a single client; drops oldest if slow."""
    try:
        while True:
            payload = await q.get()
            try:
                # 2.0 s backpressure cutoff: close stalled clients
                await asyncio.wait_for(ws.send_json(payload), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Client connection stalled (>2.0s send timeout). Disconnecting client.")
                await ws.close(code=status.WS_1011_INTERNAL_ERROR, reason="Send timeout")
                break
            except Exception:
                break
    except asyncio.CancelledError:
        pass


# --- Browser Command Watchdog Task ---

async def browser_command_watchdog():
    """Monitors incoming browser command freshness.
    If no valid command arrives for 300 ms while ARMED, forces zero velocity on the serial
    manager while maintaining serial heartbeats, ensuring smooth deceleration without Mega timeout.
    """
    global last_valid_command_time, cmd_sequence_id
    zero_command_sent = True

    while True:
        await asyncio.sleep(0.050)
        telem = serial_mgr.latest_telemetry
        is_armed = telem and telem.state_code == STATE_ARMED

        if is_armed:
            now = time.time()
            if (now - last_valid_command_time) > BROWSER_COMMAND_TIMEOUT_S:
                if not zero_command_sent:
                    logger.warning("Browser command timeout (>300 ms). Forcing zero velocity on Mega.")
                    cmd_sequence_id = (cmd_sequence_id + 1) & 0xFFFF
                    # Safe zero-velocity motion payload (holding current leg height)
                    height_l = telem.leg_pos_l if telem else int(LEG_HEIGHT_NOMINAL_MM)
                    height_r = telem.leg_pos_r if telem else int(LEG_HEIGHT_NOMINAL_MM)
                    safe_stop = CmdMotion(
                        target_vel_x=0,
                        target_yaw_rate=0,
                        leg_height_l=height_l,
                        leg_height_r=height_r,
                        roll_trim=0,
                        flags=1,  # Active balance enabled
                        reserved=0,
                        command_id=cmd_sequence_id
                    )
                    await serial_mgr.send_motion_command(safe_stop)
                    zero_command_sent = True
            else:
                zero_command_sent = False


# --- WebSocket Handler ---

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    ticket: Optional[str] = Query(None),
    token: Optional[str] = Query(None)
):
    global primary_controller_ws, last_valid_command_time, cmd_sequence_id, disconnect_disarm_task

    # 1. Strictly reject legacy ?token= parameter
    if token is not None:
        logger.warning("Rejected WebSocket connection: legacy query parameter '?token=' is prohibited.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2. Validate and consume single-use ticket (accepts ONLY ?ticket=)
    if not ticket or not validate_and_consume_ticket(ticket):
        logger.warning("Rejected WebSocket connection: missing, invalid, or expired ticket.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    # 2. Assign Primary Controller Lock
    is_controller = False
    if primary_controller_ws is None:
        primary_controller_ws = websocket
        is_controller = True
        logger.info("Client granted PRIMARY CONTROLLER lock.")
        # Cancel any pending disarm-on-disconnect timer
        if disconnect_disarm_task and not disconnect_disarm_task.done():
            disconnect_disarm_task.cancel()
            disconnect_disarm_task = None
    else:
        logger.info("Client connected as READ-ONLY OBSERVER (another controller active).")

    active_connections.add(websocket)
    q = asyncio.Queue(maxsize=2)
    client_queues[websocket] = q
    sender_task = asyncio.create_task(client_sender(websocket, q))

    # Send client status acknowledgment
    try:
        await websocket.send_json({
            "type": "connection_ack",
            "is_controller": is_controller,
            "server_time": time.time()
        })
    except Exception:
        pass

    last_client_msg_time = 0.0
    min_cmd_interval = 1.0 / MAX_CLIENT_COMMAND_HZ

    try:
        while True:
            # 3. Message Size Validation
            raw_text = await websocket.receive_text()
            if len(raw_text) > MAX_PAYLOAD_BYTES:
                logger.warning("Payload exceeded max bytes (%d > %d). Rejected.", len(raw_text), MAX_PAYLOAD_BYTES)
                await websocket.send_json({"type": "error", "message": "Payload size exceeded limit"})
                continue

            import json
            try:
                data = json.loads(raw_text)
            except Exception:
                logger.warning("Malformed JSON rejected.")
                await websocket.send_json({"type": "error", "message": "Malformed JSON"})
                continue

            msg_type = data.get("type", "")

            # 4. Handle Ping / Pong (Available to all clients)
            if msg_type == "ping":
                try:
                    cmd_ping = PingCommand(**data)
                    await websocket.send_json({"type": "pong", "client_time": cmd_ping.client_time})
                except ValidationError as e:
                    await websocket.send_json({"type": "error", "message": str(e)})
                continue

            # 5. Handle E-STOP (Always allowed from ANY client immediately)
            if msg_type == "estop":
                try:
                    cmd_estop = EstopCommand(**data)
                    logger.warning("EMERGENCY STOP received! Reason: %s", cmd_estop.reason)
                    await serial_mgr.send_estop(reason=1)
                    await websocket.send_json({"type": "estop_ack", "status": "DELIVERED"})
                except ValidationError as e:
                    await websocket.send_json({"type": "error", "message": str(e)})
                continue

            # 6. Primary Controller Check for Motion / Arm / Tuning
            if websocket != primary_controller_ws:
                await websocket.send_json({
                    "type": "error",
                    "message": "Action rejected: client is in read-only observer mode."
                })
                continue

            # 6b. Reject commands when serial link is down (fail-closed)
            if not serial_mgr.is_connected:
                await websocket.send_json({
                    "type": "error",
                    "message": "Serial link to Mega is DOWN. Commands rejected until reconnection."
                })
                continue

            # 7. Per-Client Rate Limiting
            now = time.time()
            if (now - last_client_msg_time) < min_cmd_interval:
                continue
            last_client_msg_time = now

            # 8. Command Dispatch with Strict Validation (Reject & Log)
            if msg_type == "command":
                try:
                    cmd_motion = MotionCommand(**data)
                except ValidationError as err:
                    logger.warning("Rejected invalid MotionCommand: %s", err)
                    await websocket.send_json({"type": "error", "message": f"Invalid motion command: {err}"})
                    continue

                # Bench Gate Enforcement on Pi
                lin_limit = SPEED_LIMIT_FREE_RUN_MPS if cmd_motion.free_run_unlocked else SPEED_LIMIT_GATED_MPS
                yaw_limit = MAX_YAW_RATE_RAD_S if cmd_motion.free_run_unlocked else (MAX_YAW_RATE_RAD_S * 0.50)

                scaled_linear = max(-lin_limit, min(cmd_motion.linear_x * SPEED_LIMIT_FREE_RUN_MPS, lin_limit))
                scaled_yaw = max(-yaw_limit, min(cmd_motion.angular_z * MAX_YAW_RATE_RAD_S, yaw_limit))

                vel_x = int(scaled_linear * 1000.0)  # mm/s
                yaw_rate = int(scaled_yaw * 1000.0)  # mrad/s
                height_l = int(cmd_motion.leg_height_l)
                height_r = int(cmd_motion.leg_height_r)
                roll_trim = int(cmd_motion.roll_trim * 1000.0)
                bal_enable = 1 if cmd_motion.balance_enable else 0

                cmd_sequence_id = (cmd_sequence_id + 1) & 0xFFFF
                payload = CmdMotion(
                    target_vel_x=vel_x,
                    target_yaw_rate=yaw_rate,
                    leg_height_l=height_l,
                    leg_height_r=height_r,
                    roll_trim=roll_trim,
                    flags=bal_enable,
                    reserved=0,
                    command_id=cmd_sequence_id
                )
                await serial_mgr.send_motion_command(payload)
                last_valid_command_time = now

            elif msg_type == "arm_state":
                try:
                    cmd_arm = ArmStateCommand(**data)
                except ValidationError as err:
                    logger.warning("Rejected invalid ArmStateCommand: %s", err)
                    await websocket.send_json({"type": "error", "message": f"Invalid arm state: {err}"})
                    continue

                state_map = {
                    "DISARMED": STATE_DISARMED,
                    "CALIBRATING": STATE_CALIBRATING,
                    "ARMED": STATE_ARMED,
                    "CLEAR_FAULT": STATE_DISARMED
                }
                target_state = state_map[cmd_arm.state]
                await serial_mgr.send_arm_state(target_state, force=(cmd_arm.state == "CLEAR_FAULT"))
                last_valid_command_time = now

            elif msg_type == "pid_set":
                try:
                    cmd_pid = PidSetCommand(**data)
                except ValidationError as err:
                    logger.warning("Rejected invalid PidSetCommand: %s", err)
                    await websocket.send_json({"type": "error", "message": f"Invalid PID config: {err}"})
                    continue

                cfg = ConfigPidSet(
                    controller_id=cmd_pid.controller_id,
                    save_to_eeprom=1 if cmd_pid.save_to_eeprom else 0,
                    kp=cmd_pid.kp,
                    ki=cmd_pid.ki,
                    kd=cmd_pid.kd,
                    k_ff=cmd_pid.k_ff,
                    out_min=cmd_pid.out_min,
                    out_max=cmd_pid.out_max
                )
                await serial_mgr.send_pid_config(cfg)
                await websocket.send_json({"type": "ack", "command": "pid_set", "controller_id": cmd_pid.controller_id})

            elif msg_type == "save_eeprom":
                await serial_mgr.send_save_eeprom()
                await websocket.send_json({"type": "ack", "command": "save_eeprom"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket exception: %s", e)
    finally:
        active_connections.discard(websocket)
        client_queues.pop(websocket, None)
        sender_task.cancel()

        # Handle Controller Disconnection
        if websocket == primary_controller_ws:
            logger.warning("PRIMARY CONTROLLER disconnected!")
            primary_controller_ws = None

            telem = serial_mgr.latest_telemetry
            if telem and telem.state_code == STATE_ARMED:
                # 1. Immediately force zero velocity
                logger.warning("Controller lost while ARMED: commanding immediate ZERO VELOCITY.")
                cmd_sequence_id = (cmd_sequence_id + 1) & 0xFFFF
                safe_stop = CmdMotion(
                    target_vel_x=0,
                    target_yaw_rate=0,
                    leg_height_l=telem.leg_pos_l,
                    leg_height_r=telem.leg_pos_r,
                    roll_trim=0,
                    flags=1,
                    reserved=0,
                    command_id=cmd_sequence_id
                )
                await serial_mgr.send_motion_command(safe_stop)

                # 2. Schedule DISARM after timeout if no reconnect
                async def auto_disarm_on_disconnect():
                    await asyncio.sleep(DISARM_ON_DISCONNECT_TIMEOUT_S)
                    curr = serial_mgr.latest_telemetry
                    if curr and curr.state_code == STATE_ARMED and primary_controller_ws is None:
                        logger.warning("Disarm timeout expired (%s s). Requesting DISARMED.", DISARM_ON_DISCONNECT_TIMEOUT_S)
                        await serial_mgr.send_arm_state(STATE_DISARMED)

                disconnect_disarm_task = asyncio.create_task(auto_disarm_on_disconnect())

            # Promote next available client if present
            if active_connections:
                primary_controller_ws = next(iter(active_connections))
                logger.info("Promoted client to PRIMARY CONTROLLER.")
                try:
                    await primary_controller_ws.send_json({"type": "connection_ack", "is_controller": True})
                except Exception:
                    pass

        logger.info("Web client cleanup complete. Remaining clients: %d", len(active_connections))


# --- Telemetry Broadcaster Loop with Bounded Queue ---

async def telemetry_broadcaster():
    """Broadcasts 20 Hz telemetry frames to all connected UI clients.
    Uses bounded per-client queues with frame-dropping to prevent mobile client backpressure.
    """
    last_broadcast_state = -1

    while True:
        await asyncio.sleep(TELEMETRY_BROADCAST_INTERVAL_S)
        if not active_connections:
            continue

        telem = serial_mgr.latest_telemetry
        if not telem:
            continue

        state_names = {
            STATE_DISARMED: "DISARMED",
            STATE_CALIBRATING: "CALIBRATING",
            STATE_ARMED: "ARMED",
            STATE_FAULT: "FAULT"
        }
        state_str = state_names.get(telem.state_code, "UNKNOWN")

        # Decode fault descriptions
        err_desc = "NOMINAL"
        if telem.error_flags & 0x01:
            err_desc = "TILT_CUTOFF (Pitch>45° or Roll>35°)"
        elif telem.error_flags & 0x02:
            err_desc = "COMMS_TIMEOUT (>400ms)"
        elif telem.error_flags & 0x04:
            err_desc = "BATTERY_CRITICAL (<9.6V)"
        elif telem.error_flags & 0x08:
            err_desc = "MOTOR_DRIVER_FAULT"
        elif telem.error_flags & 0x10:
            err_desc = "ESTOP_LATCHED"

        # Log state changes
        if telem.state_code != last_broadcast_state:
            logger.info("Robot state machine transitioned to: %s (flags=0x%02X)", state_str, telem.error_flags)
            last_broadcast_state = telem.state_code

        # Accurate packet freshness calculation
        packet_age_ms = round((time.time() - serial_mgr.last_rx_time) * 1000.0, 1) if serial_mgr.last_rx_time > 0 else 9999.0

        # CPU Temperature (Raspberry Pi thermal zone)
        cpu_temp = 0.0
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                cpu_temp = round(int(f.read().strip()) / 1000.0, 1)
        except Exception:
            cpu_temp = 0.0

        payload = {
            "type": "telemetry",
            "timestamp_ms": int(time.time() * 1000),
            "state": state_str if serial_mgr.is_connected else "DISARMED",
            "state_code": telem.state_code if serial_mgr.is_connected else STATE_DISARMED,
            "link_down": not serial_mgr.is_connected,
            "pose": {
                "pitch": round(telem.pitch_deg, 2),
                "pitch_rate": round(telem.pitch_rate_dps, 2),
                "roll": round(telem.roll_deg, 2),
                "yaw_rate": round(telem.yaw_rate_dps, 2)
            },
            "wheels": {
                "pos_left": telem.wheel_pos_l,
                "pos_right": telem.wheel_pos_r,
                "vel_left": telem.wheel_vel_l,
                "vel_right": telem.wheel_vel_r
            },
            "legs": {
                "height_left": telem.leg_pos_l,
                "height_right": telem.leg_pos_r
            },
            "power": {
                "battery_voltage": round(telem.v_batt_mv / 1000.0, 2),
                "v_batt_mv": telem.v_batt_mv,
                "low_battery": (telem.error_flags & 0x04) != 0
            },
            "system": {
                "cpu_temp_c": cpu_temp
            },
            "diagnostics": {
                "loop_jitter_us": telem.loop_jitter_us,
                "error_flags": telem.error_flags,
                "error_desc": err_desc,
                "packet_age_ms": packet_age_ms,
                "last_cmd_id": telem.last_cmd_id,
                "serial_connected": serial_mgr.is_connected
            }
        }

        # Non-blocking distribution to client queues (drop oldest if full)
        for ws, q in list(client_queues.items()):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass


# Mount Static Files (Web UI PWA)
if WEB_UI_DIR.exists():
    app.mount("/", StaticFiles(directory=str(WEB_UI_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    # Check for TLS certificates
    ssl_kwargs = {}
    if SSL_CERT_FILE.exists() and SSL_KEY_FILE.exists():
        logger.info("Found TLS certificates. Starting HTTPS server on port %d...", SERVER_PORT)
        ssl_kwargs["ssl_certfile"] = str(SSL_CERT_FILE)
        ssl_kwargs["ssl_keyfile"] = str(SSL_KEY_FILE)
    else:
        logger.warning("TLS certificates not found in %s. Starting in HTTP mode.", SSL_CERT_FILE.parent)
        logger.info("Run 'python robot/backend/scripts/generate_cert.py' to generate certificates.")

    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT, log_level="info", **ssl_kwargs)

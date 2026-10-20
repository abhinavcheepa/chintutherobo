"""
CHINTU Robot Control Dashboard - Backend Server
Supports:
1. WebSocket (real-time telemetry & commands)
2. REST API (command/polling/configuration)
3. Hardware Serial Bridge (Raspberry Pi <-> ESP32 / Arduino / Microcontroller)
4. Auto-detection of USB & UART ports on Raspberry Pi and PC
"""

import asyncio
import os
import json
import time
import math
import random
import logging
import argparse
import threading
from datetime import datetime

# Try to import websockets
try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

# Try to import aiohttp
try:
    from aiohttp import web
except ImportError:
    print("Installing aiohttp...")
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
    from aiohttp import web

# Try to import pyserial
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('chintu-server')


# ============ SERIAL HARDWARE BRIDGE (Raspberry Pi & PC) ============
class SerialBridge:
    """Manages serial communication with ESP32 / Arduino / Microcontroller on Raspberry Pi or PC."""

    def __init__(self, robot_state):
        self.robot = robot_state
        self.ser = None
        self.port = None
        self.baud = 115200
        self.is_connected = False
        self.rx_packets = 0
        self.tx_packets = 0
        self.last_rx_time = 0
        self.last_error = None
        self._stop_event = threading.Event()
        self._thread = None

    def list_ports(self):
        """List all available serial / USB ports on the system."""
        if not SERIAL_AVAILABLE:
            return []
        ports = []
        for p in serial.tools.list_ports.comports():
            ports.append({
                'device': p.device,
                'description': p.description,
                'hwid': p.hwid,
                'is_robot_candidate': any(k in p.description.lower() or k in p.device.lower()
                                          for k in ['ch340', 'cp210', 'ftdi', 'usb', 'serial', 'acm', 'ttyusb'])
            })
        return ports

    def auto_find_port(self):
        """Automatically find best candidate serial port for ESP32 / robot."""
        ports = self.list_ports()
        if not ports:
            return None
        # Prioritize USB serial adapters / ttyUSB / ttyACM
        for p in ports:
            if p['is_robot_candidate']:
                return p['device']
        return ports[0]['device']

    def connect(self, port=None, baud=115200):
        """Connect to a serial port."""
        if not SERIAL_AVAILABLE:
            self.last_error = "pyserial library is not installed"
            logger.error(self.last_error)
            return False

        if self.is_connected:
            self.disconnect()

        target_port = port or self.auto_find_port()
        if not target_port:
            self.last_error = "No serial ports found"
            logger.warning(f"⚠️ {self.last_error}")
            return False

        try:
            self.baud = int(baud)
            self.port = target_port
            self.ser = serial.Serial(self.port, self.baud, timeout=1.0)
            self.is_connected = True
            self.last_error = None
            self._stop_event.clear()

            # Start background reader thread
            self._thread = threading.Thread(target=self._reader_loop, daemon=True)
            self._thread.start()

            logger.info(f"✅ Hardware Serial Connected: {self.port} at {self.baud} baud")

            # Send initial ping / handshake
            self.send_command({'type': 'handshake', 'source': 'raspberrypi-server'})
            return True
        except Exception as e:
            self.last_error = str(e)
            self.is_connected = False
            self.ser = None
            logger.error(f"❌ Failed to connect to serial port {target_port}: {e}")
            return False

    def disconnect(self):
        """Disconnect the active serial port."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass

        self.ser = None
        self.is_connected = False
        self.robot.is_hardware = False
        logger.info(f"🔌 Serial disconnected: {self.port}")
        return True

    def send_command(self, cmd_dict):
        """Transmit a command dictionary as JSON over serial."""
        if not self.is_connected or not self.ser or not self.ser.is_open:
            return False
        try:
            line = json.dumps(cmd_dict) + '\n'
            self.ser.write(line.encode('utf-8'))
            self.tx_packets += 1
            return True
        except Exception as e:
            logger.error(f"Error writing to serial: {e}")
            self.last_error = str(e)
            return False

    def _reader_loop(self):
        """Continuously read lines from serial port and update robot state."""
        logger.info(f"Serial reader thread started on {self.port}")
        while not self._stop_event.is_set() and self.ser and self.ser.is_open:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                # Try parsing as JSON telemetry from ESP32
                if line.startswith('{') and line.endswith('}'):
                    try:
                        data = json.loads(line)
                        self._process_telemetry_packet(data)
                        self.rx_packets += 1
                        self.last_rx_time = time.time()
                    except json.JSONDecodeError:
                        pass
                else:
                    logger.debug(f"[SERIAL RAW] {line}")

            except serial.SerialException as e:
                logger.error(f"Serial read error: {e}")
                self.last_error = str(e)
                self.is_connected = False
                break
            except Exception as e:
                logger.error(f"Unexpected serial error: {e}")
                time.sleep(0.1)

        self.is_connected = False
        self.robot.is_hardware = False
        logger.info("Serial reader thread terminated")

    def _process_telemetry_packet(self, data):
        """Update robot state directly with live hardware sensor data."""
        self.robot.is_hardware = True
        self.robot.last_hardware_time = time.time()

        if 'pitch' in data:
            self.robot.pitch = float(data['pitch'])
        if 'pitchRate' in data:
            self.robot.pitch_rate = float(data['pitchRate'])
        if 'leftHip' in data:
            self.robot.left_hip = float(data['leftHip'])
        if 'rightHip' in data:
            self.robot.right_hip = float(data['rightHip'])
        if 'leftKnee' in data:
            self.robot.left_knee = float(data['leftKnee'])
        if 'rightKnee' in data:
            self.robot.right_knee = float(data['rightKnee'])
        if 'leftWheelRPM' in data:
            self.robot.left_wheel_rpm = float(data['leftWheelRPM'])
        if 'rightWheelRPM' in data:
            self.robot.right_wheel_rpm = float(data['rightWheelRPM'])
        if 'power' in data:
            self.robot.power = float(data['power'])
        if 'temp' in data:
            self.robot.temp = float(data['temp'])


# ============ ROBOT STATE ============
class RobotState:
    """Shared robot state accessible by WebSocket, REST, and Serial Hardware handlers."""

    def __init__(self):
        self.reset()
        self.connected_clients = set()
        self.command_queue = asyncio.Queue()
        self.start_time = time.time()
        self.is_hardware = False
        self.last_hardware_time = 0

    def reset(self):
        self.pitch = 0.0
        self.pitch_rate = 0.0
        self.left_hip = 0.0
        self.right_hip = 0.0
        self.left_knee = 0.0
        self.right_knee = 0.0
        self.left_wheel_rpm = 0.0
        self.right_wheel_rpm = 0.0
        self.left_wheel_torque = 0.0
        self.right_wheel_torque = 0.0
        self.com_x = 0.0
        self.com_y = 0.4
        self.power = 100.0
        self.temp = 28.0
        self.direction = None
        self.speed = 50
        self.balance_mode = False
        self.pid = {'kp': 10.0, 'ki': 0.5, 'kd': 2.0}
        self.pid_integral = 0.0
        self.pid_last_error = 0.0
        self.sim_running = True

    def to_dict(self):
        return {
            'pitch': round(self.pitch, 3),
            'pitchRate': round(self.pitch_rate, 3),
            'leftHip': round(self.left_hip, 2),
            'rightHip': round(self.right_hip, 2),
            'leftKnee': round(self.left_knee, 2),
            'rightKnee': round(self.right_knee, 2),
            'leftWheelRPM': round(self.left_wheel_rpm, 1),
            'rightWheelRPM': round(self.right_wheel_rpm, 1),
            'leftWheelTorque': round(self.left_wheel_torque, 2),
            'rightWheelTorque': round(self.right_wheel_torque, 2),
            'comX': round(self.com_x, 4),
            'comY': round(self.com_y, 4),
            'power': round(self.power, 1),
            'temp': round(self.temp, 1),
            'uptime': round(time.time() - self.start_time, 1),
            'timestamp': time.time(),
            'isHardware': self.is_hardware,
            'hardwarePort': serial_bridge.port if serial_bridge.is_connected else None,
        }

    def step(self, dt=0.02):
        """Step physics simulation if real hardware is not feeding live telemetry."""
        if self.is_hardware:
            # Check watchdog timer: if hardware silent for > 3.0s, fall back to sim
            if time.time() - self.last_hardware_time > 3.0:
                logger.warning("⚠️ No hardware packet for >3s. Falling back to simulation mode.")
                self.is_hardware = False
            else:
                # Update trajectory tracking based on real wheel RPM
                self.com_x += (self.left_wheel_rpm + self.right_wheel_rpm) * 0.0001 * dt
                self.com_y = 0.4 + math.sin(math.radians(self.pitch)) * 0.2
                return

        if not self.sim_running:
            return

        gravity = 9.81
        pendulum_length = 0.5
        mass = 5.0
        speed_factor = self.speed / 100.0

        # External torque from direction
        external_torque = 0.0
        if self.direction == 'forward':
            external_torque = -2.0 * speed_factor
        elif self.direction == 'backward':
            external_torque = 2.0 * speed_factor
        elif self.direction == 'left':
            external_torque = -0.5 * speed_factor
        elif self.direction == 'right':
            external_torque = 0.5 * speed_factor

        # Pitch dynamics
        pitch_rad = math.radians(self.pitch)
        pitch_accel = (gravity / pendulum_length) * math.sin(pitch_rad) + \
                      external_torque / (mass * pendulum_length ** 2)

        # PID balance control
        if self.balance_mode:
            error = 0 - self.pitch
            self.pid_integral += error * dt
            self.pid_integral = max(-50, min(50, self.pid_integral))
            derivative = (error - self.pid_last_error) / dt if dt > 0 else 0
            control = self.pid['kp'] * error + self.pid['ki'] * self.pid_integral + self.pid['kd'] * derivative
            self.pid_last_error = error

            wheel_torque = max(-20, min(20, control))
            self.left_wheel_torque += (wheel_torque - self.left_wheel_torque) * 0.3
            self.right_wheel_torque += (wheel_torque - self.right_wheel_torque) * 0.3
            pitch_accel -= control * 0.1

        # Update pitch
        self.pitch_rate += pitch_accel * dt
        self.pitch_rate *= 0.98  # damping
        self.pitch += self.pitch_rate * dt
        self.pitch = max(-45, min(45, self.pitch))

        # Noise
        noise = lambda: random.uniform(-0.3, 0.3)

        # Wheel speeds
        target_left = target_right = 0.0
        if self.direction == 'forward':
            target_left = target_right = 120 * speed_factor
        elif self.direction == 'backward':
            target_left = target_right = -120 * speed_factor
        elif self.direction == 'left':
            target_left, target_right = -60 * speed_factor, 60 * speed_factor
        elif self.direction == 'right':
            target_left, target_right = 60 * speed_factor, -60 * speed_factor

        self.left_wheel_rpm += (target_left + noise() - self.left_wheel_rpm) * 0.1
        self.right_wheel_rpm += (target_right + noise() - self.right_wheel_rpm) * 0.1

        if not self.balance_mode:
            self.left_wheel_torque += (self.left_wheel_rpm * 0.08 + noise() - self.left_wheel_torque) * 0.2
            self.right_wheel_torque += (self.right_wheel_rpm * 0.08 + noise() - self.right_wheel_torque) * 0.2

        # COM trajectory
        self.com_x += (self.left_wheel_rpm + self.right_wheel_rpm) * 0.0001 * dt
        self.com_y = 0.4 + math.sin(math.radians(self.pitch)) * 0.2

        # Temperature & power
        self.temp = max(25, min(65, self.temp + random.uniform(-0.05, 0.08)))
        self.power = max(0, min(100, self.power - random.uniform(0, 0.02)))

    def handle_command(self, cmd):
        """Process incoming command and forward to real hardware if connected."""
        cmd_type = cmd.get('type', '')

        # Forward command to real hardware over Serial (Raspberry Pi -> ESP32)
        if serial_bridge.is_connected:
            serial_bridge.send_command(cmd)

        if cmd_type == 'move':
            direction = cmd.get('direction', 'stop')
            self.direction = direction if direction != 'stop' else None
            self.speed = cmd.get('speed', self.speed)
            logger.info(f"Move: {direction}, Speed: {self.speed} (Hardware: {self.is_hardware})")

        elif cmd_type == 'speed':
            self.speed = cmd.get('value', 50)
            logger.info(f"Speed: {self.speed}")

        elif cmd_type == 'joint':
            joint = cmd.get('joint', '')
            angle = cmd.get('angle', 0)
            if 'LHip' in joint: self.left_hip = angle
            elif 'RHip' in joint: self.right_hip = angle
            elif 'LKnee' in joint: self.left_knee = angle
            elif 'RKnee' in joint: self.right_knee = angle
            logger.info(f"Joint {joint}: {angle}°")

        elif cmd_type == 'pid':
            self.pid['kp'] = cmd.get('kp', self.pid['kp'])
            self.pid['ki'] = cmd.get('ki', self.pid['ki'])
            self.pid['kd'] = cmd.get('kd', self.pid['kd'])
            self.pid_integral = 0
            logger.info(f"PID: Kp={self.pid['kp']}, Ki={self.pid['ki']}, Kd={self.pid['kd']}")

        elif cmd_type == 'control':
            mode = cmd.get('mode', 'manual')
            self.balance_mode = (mode == 'balance')
            logger.info(f"Control mode: {mode}")

        elif cmd_type == 'stance':
            stance = cmd.get('stance', 'stand')
            logger.info(f"Stance: {stance}")
            if stance == 'stand':
                self.left_hip = 0.0; self.right_hip = 0.0
                self.left_knee = 0.0; self.right_knee = 0.0
            elif stance == 'crouch':
                self.left_hip = 30.0; self.right_hip = 30.0
                self.left_knee = -60.0; self.right_knee = -60.0
            elif stance == 'tilt_fwd':
                self.left_hip = -20.0; self.right_hip = -20.0
            elif stance == 'tilt_back':
                self.left_hip = 20.0; self.right_hip = 20.0
            elif stance == 'estop':
                self.direction = None
                self.balance_mode = False

        elif cmd_type == 'estop':
            self.direction = None
            self.balance_mode = False
            logger.warning("🚨 EMERGENCY STOP TRIGGERED: Motors cut")

        elif cmd_type == 'sim':
            action = cmd.get('action', '')
            if action == 'play':
                self.sim_running = True
            elif action == 'pause':
                self.sim_running = False
            elif action == 'reset':
                self.reset()
            elif action == 'step':
                self.step(0.02)
            logger.info(f"Sim action: {action}")

        elif cmd_type == 'raw':
            logger.info(f"Raw command: {cmd.get('command', '')}")

        return {'status': 'ok', 'type': cmd_type, 'hardware': self.is_hardware}


# Global instances
robot = RobotState()
serial_bridge = SerialBridge(robot)


# ============ WEBSOCKET SERVER ============
async def ws_handler(websocket):
    """Handle a single WebSocket connection from browser or Raspberry Pi client."""
    robot.connected_clients.add(websocket)
    logger.info(f"WebSocket client connected ({len(robot.connected_clients)} total)")

    try:
        # Send initial welcome state
        await websocket.send(json.dumps({
            'type': 'welcome',
            'message': 'Connected to Chintu Robot Server (Raspberry Pi / Hybrid)',
            **robot.to_dict()
        }))

        async for message in websocket:
            try:
                cmd = json.loads(message)
                result = robot.handle_command(cmd)
                await websocket.send(json.dumps(result))

                # Broadcast command to other connected hardware clients
                cmd_json = json.dumps(cmd)
                for client in robot.connected_clients:
                    if client != websocket:
                        try:
                            await client.send(cmd_json)
                        except websockets.ConnectionClosed:
                            pass

            except json.JSONDecodeError:
                await websocket.send(json.dumps({'error': 'Invalid JSON'}))

    except websockets.ConnectionClosed:
        pass
    finally:
        robot.connected_clients.discard(websocket)
        logger.info(f"WebSocket client disconnected ({len(robot.connected_clients)} total)")


async def ws_broadcast_loop():
    """Periodically broadcast telemetry to all connected WebSocket clients."""
    while True:
        robot.step(0.02)

        if robot.connected_clients:
            data = json.dumps(robot.to_dict())
            disconnected = set()
            for client in robot.connected_clients:
                try:
                    await client.send(data)
                except websockets.ConnectionClosed:
                    disconnected.add(client)
            robot.connected_clients -= disconnected

        await asyncio.sleep(0.05)  # 20Hz update


# ============ REST API SERVER ============
async def handle_ping(request):
    return web.json_response({
        'status': 'ok',
        'server': 'chintu-robot',
        'device': 'Raspberry Pi / Host',
        'isHardware': robot.is_hardware,
        'uptime': round(time.time() - robot.start_time, 1)
    })


async def handle_telemetry(request):
    return web.json_response(robot.to_dict())


async def handle_command(request):
    try:
        cmd = await request.json()
        result = robot.handle_command(cmd)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=400)


async def handle_status(request):
    return web.json_response({
        **robot.to_dict(),
        'connected_clients': len(robot.connected_clients),
        'balance_mode': robot.balance_mode,
        'direction': robot.direction,
        'speed': robot.speed,
        'pid': robot.pid,
        'serial': {
            'available': SERIAL_AVAILABLE,
            'connected': serial_bridge.is_connected,
            'port': serial_bridge.port,
            'baud': serial_bridge.baud,
            'rx_packets': serial_bridge.rx_packets,
            'tx_packets': serial_bridge.tx_packets,
            'last_error': serial_bridge.last_error
        }
    })


async def handle_reset(request):
    robot.reset()
    return web.json_response({'status': 'ok', 'message': 'Robot state reset'})


# Serial Bridge REST Handlers
async def handle_serial_ports(request):
    ports = serial_bridge.list_ports()
    return web.json_response({
        'available': SERIAL_AVAILABLE,
        'ports': ports,
        'connected_port': serial_bridge.port if serial_bridge.is_connected else None
    })


async def handle_serial_connect(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    port = data.get('port')
    baud = data.get('baud', 115200)

    success = serial_bridge.connect(port=port, baud=baud)
    if success:
        return web.json_response({
            'status': 'ok',
            'message': f'Connected to {serial_bridge.port}',
            'port': serial_bridge.port,
            'baud': serial_bridge.baud
        })
    else:
        return web.json_response({
            'status': 'error',
            'message': serial_bridge.last_error or 'Failed to connect to serial port'
        }, status=400)


async def handle_serial_disconnect(request):
    serial_bridge.disconnect()
    return web.json_response({'status': 'ok', 'message': 'Serial disconnected'})


async def handle_serial_status(request):
    return web.json_response({
        'available': SERIAL_AVAILABLE,
        'connected': serial_bridge.is_connected,
        'port': serial_bridge.port,
        'baud': serial_bridge.baud,
        'rx_packets': serial_bridge.rx_packets,
        'tx_packets': serial_bridge.tx_packets,
        'last_error': serial_bridge.last_error
    })


def create_rest_app():
    """Create the REST API application with CORS and static files."""
    app = web.Application()

    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == 'OPTIONS':
            response = web.Response()
        else:
            response = await handler(request)

        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    app.middlewares.append(cors_middleware)

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    async def handle_index(request):
        return web.FileResponse(os.path.join(BASE_DIR, 'index.html'))

    async def handle_css(request):
        return web.FileResponse(os.path.join(BASE_DIR, 'index.css'))

    # API Endpoints
    app.router.add_get('/api/ping', handle_ping)
    app.router.add_get('/api/telemetry', handle_telemetry)
    app.router.add_post('/api/command', handle_command)
    app.router.add_get('/api/status', handle_status)
    app.router.add_post('/api/reset', handle_reset)

    # Serial Endpoints (for Raspberry Pi & PC)
    app.router.add_get('/api/serial/ports', handle_serial_ports)
    app.router.add_post('/api/serial/connect', handle_serial_connect)
    app.router.add_post('/api/serial/disconnect', handle_serial_disconnect)
    app.router.add_get('/api/serial/status', handle_serial_status)

    # Static Web Dashboard
    app.router.add_get('/', handle_index)
    app.router.add_get('/index.html', handle_index)
    app.router.add_get('/index.css', handle_css)
    js_dir = os.path.join(BASE_DIR, 'js')
    if os.path.isdir(js_dir):
        app.router.add_static('/js', path=js_dir)

    return app


# ============ MAIN ============
async def main():
    parser = argparse.ArgumentParser(description="Chintu Robot Backend & Raspberry Pi Bridge")
    parser.add_argument('--host', default='0.0.0.0', help="Host address (default 0.0.0.0)")
    parser.add_argument('--port', type=int, default=8973, help="REST API & Web UI port (default 8973)")
    parser.add_argument('--ws-port', type=int, default=8765, help="WebSocket port (default 8765)")
    parser.add_argument('--serial', default=None, help="Connect directly to serial port (e.g. /dev/ttyUSB0 or COM3)")
    parser.add_argument('--baud', type=int, default=115200, help="Serial baud rate (default 115200)")
    parser.add_argument('--auto-serial', action='store_true', help="Auto-connect to detected ESP32 / robot on startup")
    args = parser.parse_args()

    # Attempt serial connection if requested
    if args.serial:
        serial_bridge.connect(port=args.serial, baud=args.baud)
    elif args.auto_serial:
        logger.info("Scanning for connected robot on serial ports...")
        serial_bridge.connect(baud=args.baud)

    # Start WebSocket server
    ws_server = await websockets.serve(ws_handler, args.host, args.ws_port)
    logger.info(f"✅ WebSocket server running on ws://{args.host}:{args.ws_port}")

    # Start broadcast loop
    broadcast_task = asyncio.create_task(ws_broadcast_loop())

    # Start REST & Web Dashboard server
    rest_app = create_rest_app()
    runner = web.AppRunner(rest_app)
    await runner.setup()
    rest_site = web.TCPSite(runner, args.host, args.port)
    await rest_site.start()
    logger.info(f"✅ Web Dashboard & REST server running on http://{args.host}:{args.port}")

    logger.info("=" * 65)
    logger.info("  🤖 CHINTU Robot Control Platform & Raspberry Pi Bridge")
    logger.info(f"  👉 Web Dashboard:  http://localhost:{args.port}")
    logger.info(f"  👉 REST API:        http://localhost:{args.port}/api")
    logger.info(f"  👉 WebSocket:       ws://localhost:{args.ws_port}")
    if serial_bridge.is_connected:
        logger.info(f"  👉 Hardware Serial: {serial_bridge.port} ({serial_bridge.baud} baud) [CONNECTED]")
    else:
        logger.info("  👉 Hardware Serial: Standby / Simulation mode")
    logger.info("=" * 65)

    # Keep running forever
    await asyncio.gather(broadcast_task, asyncio.Future())


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        if serial_bridge.is_connected:
            serial_bridge.disconnect()
        logger.info("Server shutting down cleanly...")

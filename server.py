"""
CHINTU Robot Control Dashboard - Backend Server
Supports WebSocket (real-time) + REST API (command/polling)
Run: python server.py
Requirements: pip install websockets aiohttp
"""

import asyncio
import json
import time
import math
import random
import logging
from datetime import datetime

# Try to import dependencies
try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

try:
    from aiohttp import web
except ImportError:
    print("Installing aiohttp...")
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "aiohttp"])
    from aiohttp import web

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('chintu-server')

# ============ ROBOT STATE ============
class RobotState:
    """Shared robot state accessible by both WebSocket and REST handlers."""

    def __init__(self):
        self.reset()
        self.connected_clients = set()
        self.command_queue = asyncio.Queue()
        self.start_time = time.time()

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
        }

    def step(self, dt=0.02):
        """Simulate one physics step."""
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
        """Process an incoming command."""
        cmd_type = cmd.get('type', '')

        if cmd_type == 'move':
            direction = cmd.get('direction', 'stop')
            self.direction = direction if direction != 'stop' else None
            self.speed = cmd.get('speed', self.speed)
            logger.info(f"Move: {direction}, Speed: {self.speed}")

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
            self.pid_integral = 0  # reset on change
            logger.info(f"PID: Kp={self.pid['kp']}, Ki={self.pid['ki']}, Kd={self.pid['kd']}")

        elif cmd_type == 'control':
            mode = cmd.get('mode', 'manual')
            self.balance_mode = (mode == 'balance')
            logger.info(f"Control mode: {mode}")

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

        return {'status': 'ok', 'type': cmd_type}


# Global robot state
robot = RobotState()


# ============ WEBSOCKET SERVER ============
async def ws_handler(websocket):
    """Handle a single WebSocket connection."""
    client_id = id(websocket)
    robot.connected_clients.add(websocket)
    logger.info(f"WebSocket client connected ({len(robot.connected_clients)} total)")

    try:
        # Send initial state
        await websocket.send(json.dumps({
            'type': 'welcome',
            'message': 'Connected to Chintu Robot Server',
            **robot.to_dict()
        }))

        async for message in websocket:
            try:
                cmd = json.loads(message)
                result = robot.handle_command(cmd)
                await websocket.send(json.dumps(result))
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
            # Broadcast to all connected clients
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
    return web.json_response({'status': 'ok', 'server': 'chintu-robot', 'uptime': time.time() - robot.start_time})


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
    })


async def handle_reset(request):
    robot.reset()
    return web.json_response({'status': 'ok', 'message': 'Robot state reset'})


def create_rest_app():
    """Create the REST API application with CORS support."""
    app = web.Application()

    # CORS middleware
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

    # Routes
    app.router.add_get('/api/ping', handle_ping)
    app.router.add_get('/api/telemetry', handle_telemetry)
    app.router.add_post('/api/command', handle_command)
    app.router.add_get('/api/status', handle_status)
    app.router.add_post('/api/reset', handle_reset)

    return app


# ============ MAIN ============
async def main():
    WS_HOST = '0.0.0.0'
    WS_PORT = 8765
    REST_PORT = 8080

    # Start WebSocket server
    ws_server = await websockets.serve(ws_handler, WS_HOST, WS_PORT)
    logger.info(f"✅ WebSocket server running on ws://{WS_HOST}:{WS_PORT}")

    # Start broadcast loop
    broadcast_task = asyncio.create_task(ws_broadcast_loop())

    # Start REST server
    rest_app = create_rest_app()
    runner = web.AppRunner(rest_app)
    await runner.setup()
    rest_site = web.TCPSite(runner, WS_HOST, REST_PORT)
    await rest_site.start()
    logger.info(f"✅ REST API server running on http://{WS_HOST}:{REST_PORT}/api")

    logger.info("=" * 60)
    logger.info("  CHINTU Robot Control Server is READY")
    logger.info(f"  WebSocket:  ws://localhost:{WS_PORT}")
    logger.info(f"  REST API:   http://localhost:{REST_PORT}/api")
    logger.info(f"  Dashboard:  Open index.html in your browser")
    logger.info("=" * 60)

    # Keep running forever
    await asyncio.gather(broadcast_task, asyncio.Future())


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutting down...")

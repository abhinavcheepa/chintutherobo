#!/usr/bin/env python3
"""
CHINTU — Mock ESP32 Simulator
Used by the Raspberry Pi developer to test button presses and UI commands
WITHOUT needing physical ESP32 hardware!

Run:
    python mock_esp32.py
"""

import time
import math
import json
import sys
import logging
import asyncio

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [MOCK-ESP32] %(message)s')
logger = logging.getLogger('mock-esp32')

class MockESP32:
    def __init__(self):
        self.pitch = 0.0
        self.pitch_rate = 0.0
        self.speed = 50
        self.direction = "stop"
        self.left_hip = 0.0
        self.right_hip = 0.0
        self.left_knee = 0.0
        self.right_knee = 0.0
        self.left_rpm = 0.0
        self.right_rpm = 0.0
        self.balance_mode = False
        self.kp = 10.0
        self.ki = 0.5
        self.kd = 2.0

    def process_command(self, cmd):
        cmd_type = cmd.get("type", "")

        if cmd_type == "move":
            self.direction = cmd.get("direction", "stop")
            self.speed = cmd.get("speed", self.speed)
            pwm = int((self.speed / 100.0) * 255)

            if self.direction == "forward":
                self.left_rpm = (self.speed / 100.0) * 150
                self.right_rpm = (self.speed / 100.0) * 150
                logger.info(f"🟢 [WHEELS FORWARD] Speed: {self.speed}% | PWM: {pwm}")
            elif self.direction == "backward":
                self.left_rpm = -(self.speed / 100.0) * 150
                self.right_rpm = -(self.speed / 100.0) * 150
                logger.info(f"🔵 [WHEELS BACKWARD] Speed: {self.speed}% | PWM: -{pwm}")
            elif self.direction == "left":
                self.left_rpm = -(self.speed / 100.0) * 75
                self.right_rpm = (self.speed / 100.0) * 75
                logger.info(f"🔄 [WHEELS SPIN LEFT] L-RPM: {self.left_rpm:.1f}, R-RPM: {self.right_rpm:.1f}")
            elif self.direction == "right":
                self.left_rpm = (self.speed / 100.0) * 75
                self.right_rpm = -(self.speed / 100.0) * 75
                logger.info(f"🔄 [WHEELS SPIN RIGHT] L-RPM: {self.left_rpm:.1f}, R-RPM: {self.right_rpm:.1f}")
            else:
                self.left_rpm = 0.0
                self.right_rpm = 0.0
                logger.info("🛑 [WHEELS STOP] Motors cut to 0 RPM")

        elif cmd_type == "speed":
            self.speed = cmd.get("value", 50)
            logger.info(f"⚡ [SPEED UPDATED] Current speed set to {self.speed}%")

        elif cmd_type == "joint":
            joint = cmd.get("joint", "")
            angle = float(cmd.get("angle", 0.0))
            if "LHip" in joint: self.left_hip = angle
            elif "RHip" in joint: self.right_hip = angle
            elif "LKnee" in joint: self.left_knee = angle
            elif "RKnee" in joint: self.right_knee = angle
            logger.info(f"🦾 [SERVO MOVED] {joint} rotated to {angle:.1f}°")

        elif cmd_type == "stance":
            stance = cmd.get("stance", "stand")
            logger.info(f"🕺 [POSE APPLIED] Stance '{stance.upper()}'")
            if stance == "stand":
                self.left_hip = 0.0; self.right_hip = 0.0
                self.left_knee = 0.0; self.right_knee = 0.0
            elif stance == "crouch":
                self.left_hip = 30.0; self.right_hip = 30.0
                self.left_knee = -60.0; self.right_knee = -60.0
            elif stance == "tilt_fwd":
                self.left_hip = -20.0; self.right_hip = -20.0
            elif stance == "tilt_back":
                self.left_hip = 20.0; self.right_hip = 20.0
            elif stance == "estop":
                self.left_rpm = 0.0; self.right_rpm = 0.0
                self.direction = "stop"

        elif cmd_type == "control":
            self.balance_mode = (cmd.get("mode") == "balance")
            logger.info(f"⚖️ [BALANCE MODE] {'ON' if self.balance_mode else 'OFF'}")

        elif cmd_type == "estop":
            self.left_rpm = 0.0; self.right_rpm = 0.0
            self.direction = "stop"
            logger.warning("🚨 [EMERGENCY STOP] All motors immediately cut!")

    def get_telemetry(self):
        # Slightly oscillate pitch for realistic IMU emulation
        t = time.time()
        self.pitch = round(math.sin(t * 2.0) * 1.5, 2)
        self.pitch_rate = round(math.cos(t * 2.0) * 3.0, 2)

        return {
            "pitch": self.pitch,
            "pitchRate": self.pitch_rate,
            "leftHip": self.left_hip,
            "rightHip": self.right_hip,
            "leftKnee": self.left_knee,
            "rightKnee": self.right_knee,
            "leftWheelRPM": round(self.left_rpm, 1),
            "rightWheelRPM": round(self.right_rpm, 1),
            "power": 84.5,
            "temp": 31.8,
            "isHardware": True
        }


async def main():
    esp = MockESP32()
    uri = "ws://localhost:8765"
    logger.info(f"Connecting Mock ESP32 to server at {uri}...")

    while True:
        try:
            async with websockets.connect(uri) as ws:
                logger.info("=" * 60)
                logger.info("  🤖 MOCK ESP32 CONNECTED TO RASPBERRY PI SERVER!")
                logger.info("  👉 Now open the dashboard (http://localhost:8973)")
                logger.info("  👉 Click buttons (UP, DOWN, CROUCH, SLIDERS)")
                logger.info("  👉 Watch motor actions execute in this terminal!")
                logger.info("=" * 60)

                await ws.send(json.dumps({"type": "handshake", "client": "mock-esp32"}))

                async def telemetry_loop():
                    while True:
                        telemetry = esp.get_telemetry()
                        await ws.send(json.dumps(telemetry))
                        await asyncio.sleep(0.05)  # 20Hz

                async def command_loop():
                    async for message in ws:
                        try:
                            cmd = json.loads(message)
                            esp.process_command(cmd)
                        except json.JSONDecodeError:
                            pass

                await asyncio.gather(telemetry_loop(), command_loop())

        except Exception as e:
            logger.warning(f"Connection lost ({e}). Retrying in 2 seconds...")
            await asyncio.sleep(2.0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Mock ESP32 stopped.")

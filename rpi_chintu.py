#!/usr/bin/env python3
"""
CHINTU — Direct Raspberry Pi Onboard Controller & Hardware Daemon
Author: Chintu Robotics Team
Supports:
- Direct MPU6050 (I2C) reading on Raspberry Pi
- Motor PWM & Direction via GPIO (L298N / TB6612 / L9110S)
- Leg Joint Servo Control (50Hz RC PWM on GPIO)
- Inverted Pendulum Balance Loop on Raspberry Pi
- Full WebSocket Client syncing with server.py and Web Dashboard
"""

import time
import math
import json
import os
import sys
import logging
import argparse
import asyncio

logging.basicConfig(level=logging.INFO, format='%(asctime)s [RPI-%(levelname)s] %(message)s')
logger = logging.getLogger('rpi-chintu')

# Check for Raspberry Pi GPIO and I2C hardware libraries
try:
    import RPi.GPIO as GPIO
    RPI_GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    RPI_GPIO_AVAILABLE = False
    logger.info("RPi.GPIO not detected. Running in simulated hardware mode.")

try:
    import smbus2 as smbus
    SMBUS_AVAILABLE = True
except ImportError:
    try:
        import smbus
        SMBUS_AVAILABLE = True
    except ImportError:
        SMBUS_AVAILABLE = False
        logger.info("smbus/smbus2 not detected. I2C hardware will be simulated.")

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


# ============ MPU6050 IMU SENSOR (I2C) ============
class MPU6050:
    """I2C Driver for MPU-6050 6-DOF Accelerometer and Gyroscope on Raspberry Pi."""

    PWR_MGMT_1   = 0x6B
    SMPLRT_DIV   = 0x19
    CONFIG       = 0x1A
    GYRO_CONFIG  = 0x1B
    INT_ENABLE   = 0x38
    ACCEL_XOUT_H = 0x3B
    ACCEL_YOUT_H = 0x3D
    ACCEL_ZOUT_H = 0x3F
    GYRO_XOUT_H  = 0x43
    GYRO_YOUT_H  = 0x45
    GYRO_ZOUT_H  = 0x47

    def __init__(self, bus_num=1, address=0x68):
        self.address = address
        self.bus_num = bus_num
        self.bus = None
        self.connected = False
        self.pitch = 0.0
        self.pitch_rate = 0.0
        self.last_time = time.time()

        if SMBUS_AVAILABLE:
            try:
                self.bus = smbus.SMBus(self.bus_num)
                # Wake up MPU6050 (reset sleep mode)
                self.bus.write_byte_data(self.address, self.PWR_MGMT_1, 0)
                time.sleep(0.05)
                # Set sample rate divider to 7 (1kHz / (1+7) = 125Hz)
                self.bus.write_byte_data(self.address, self.SMPLRT_DIV, 7)
                # Set config DLPF to 42Hz
                self.bus.write_byte_data(self.address, self.CONFIG, 3)
                # Set Gyro Full Scale Range ±250 deg/s
                self.bus.write_byte_data(self.address, self.GYRO_CONFIG, 0)
                self.connected = True
                logger.info(f"✅ MPU6050 initialized on I2C bus {bus_num} at address {hex(address)}")
            except Exception as e:
                logger.warning(f"⚠️ MPU6050 initialization failed: {e}. Using fallback simulation.")
                self.connected = False

    def _read_word_2c(self, reg):
        val = (self.bus.read_byte_data(self.address, reg) << 8) + self.bus.read_byte_data(self.address, reg + 1)
        if val >= 0x8000:
            return -((65535 - val) + 1)
        return val

    def read_pitch(self):
        """Read pitch using Complementary Filter (Accel + Gyro)."""
        now = time.time()
        dt = max(0.001, min(0.1, now - self.last_time))
        self.last_time = now

        if self.connected and self.bus:
            try:
                acc_x = self._read_word_2c(self.ACCEL_XOUT_H) / 16384.0
                acc_y = self._read_word_2c(self.ACCEL_YOUT_H) / 16384.0
                acc_z = self._read_word_2c(self.ACCEL_ZOUT_H) / 16384.0
                gyro_y = self._read_word_2c(self.GYRO_YOUT_H) / 131.0  # deg/s

                # Calculate pitch from accelerometer
                acc_pitch = math.degrees(math.atan2(-acc_x, math.sqrt(acc_y*acc_y + acc_z*acc_z)))

                # Complementary filter (98% Gyro + 2% Accel)
                self.pitch_rate = gyro_y
                self.pitch = 0.98 * (self.pitch + gyro_y * dt) + 0.02 * acc_pitch
                return self.pitch, self.pitch_rate
            except Exception as e:
                logger.error(f"Error reading MPU6050: {e}")

        # Simulated fallback
        return self.pitch, self.pitch_rate


# ============ MOTOR & SERVO CONTROLLER (Raspberry Pi GPIO) ============
class RPiHardwareController:
    """Controls Wheel DC Motors & Joint RC Servos directly on Raspberry Pi GPIO."""

    def __init__(self,
                 pin_l_pwm=12, pin_l_dir=16,
                 pin_r_pwm=13, pin_r_dir=26,
                 pin_l_hip=17, pin_r_hip=27,
                 pin_l_knee=22, pin_r_knee=23):

        self.pin_l_pwm = pin_l_pwm
        self.pin_l_dir = pin_l_dir
        self.pin_r_pwm = pin_r_pwm
        self.pin_r_dir = pin_r_dir

        self.pin_l_hip = pin_l_hip
        self.pin_r_hip = pin_r_hip
        self.pin_l_knee = pin_l_knee
        self.pin_r_knee = pin_r_knee

        self.left_pwm = None
        self.right_pwm = None
        self.servo_l_hip = None
        self.servo_r_hip = None
        self.servo_l_knee = None
        self.servo_r_knee = None
        self.active = False

        if RPI_GPIO_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)

                # Setup Motor pins
                for pin in [pin_l_pwm, pin_l_dir, pin_r_pwm, pin_r_dir]:
                    GPIO.setup(pin, GPIO.OUT)

                self.left_pwm = GPIO.PWM(pin_l_pwm, 1000)  # 1kHz PWM for motors
                self.right_pwm = GPIO.PWM(pin_r_pwm, 1000)
                self.left_pwm.start(0)
                self.right_pwm.start(0)

                # Setup Servo pins (50Hz = 20ms period)
                for pin in [pin_l_hip, pin_r_hip, pin_l_knee, pin_r_knee]:
                    GPIO.setup(pin, GPIO.OUT)

                self.servo_l_hip = GPIO.PWM(pin_l_hip, 50)
                self.servo_r_hip = GPIO.PWM(pin_r_hip, 50)
                self.servo_l_knee = GPIO.PWM(pin_l_knee, 50)
                self.servo_r_knee = GPIO.PWM(pin_r_knee, 50)

                for s in [self.servo_l_hip, self.servo_r_hip, self.servo_l_knee, self.servo_r_knee]:
                    s.start(7.5) # 7.5% duty = 1.5ms = Center position

                self.active = True
                logger.info(f"✅ Raspberry Pi GPIO Hardware initialized (Motors: PWM {pin_l_pwm},{pin_r_pwm} | Servos: {pin_l_hip},{pin_r_hip},{pin_l_knee},{pin_r_knee})")
            except Exception as e:
                logger.warning(f"⚠️ Failed to init GPIO hardware: {e}")
                self.active = False

    def set_speeds(self, left_pct, right_pct):
        """Set wheel speeds from -100 to +100."""
        left_pct = max(-100, min(100, left_pct))
        right_pct = max(-100, min(100, right_pct))

        if self.active and RPI_GPIO_AVAILABLE:
            # Left motor
            if left_pct >= 0:
                GPIO.output(self.pin_l_dir, GPIO.HIGH)
                self.left_pwm.ChangeDutyCycle(left_pct)
            else:
                GPIO.output(self.pin_l_dir, GPIO.LOW)
                self.left_pwm.ChangeDutyCycle(-left_pct)

            # Right motor
            if right_pct >= 0:
                GPIO.output(self.pin_r_dir, GPIO.HIGH)
                self.right_pwm.ChangeDutyCycle(right_pct)
            else:
                GPIO.output(self.pin_r_dir, GPIO.LOW)
                self.right_pwm.ChangeDutyCycle(-right_pct)

    def set_servo_angle(self, servo_name, angle):
        """Map angle (-90 to +90 or -120 to 0) to PWM duty cycle (2.5% to 12.5%)."""
        if not self.active or not RPI_GPIO_AVAILABLE:
            return

        servo_map = {
            'LHip': (self.servo_l_hip, -90, 90),
            'RHip': (self.servo_r_hip, -90, 90),
            'LKnee': (self.servo_l_knee, -120, 0),
            'RKnee': (self.servo_r_knee, -120, 0),
        }

        entry = servo_map.get(servo_name)
        if entry:
            pwm_obj, min_a, max_a = entry
            clamped = max(min_a, min(max_a, angle))
            # Duty cycle: 2.5% (0.5ms) to 12.5% (2.5ms)
            duty = 2.5 + ((clamped - min_a) / (max_a - min_a)) * 10.0
            pwm_obj.ChangeDutyCycle(duty)

    def stop(self):
        self.set_speeds(0, 0)

    def cleanup(self):
        if self.active and RPI_GPIO_AVAILABLE:
            self.stop()
            if self.left_pwm: self.left_pwm.stop()
            if self.right_pwm: self.right_pwm.stop()
            for s in [self.servo_l_hip, self.servo_r_hip, self.servo_l_knee, self.servo_r_knee]:
                if s: s.stop()
            GPIO.cleanup()


# ============ CHINTU RASPBERRY PI MAIN CONTROLLER ============
class ChintuRpi:
    def __init__(self):
        self.imu = MPU6050()
        self.hw = RPiHardwareController()
        self.pitch = 0.0
        self.pitch_rate = 0.0
        self.balance_mode = False
        self.kp = 10.0
        self.ki = 0.5
        self.kd = 2.0
        self.pid_integral = 0.0
        self.pid_last_error = 0.0
        self.speed = 50
        self.direction = 'stop'
        self.left_hip = 0.0
        self.right_hip = 0.0
        self.left_knee = 0.0
        self.right_knee = 0.0

    def handle_command(self, cmd):
        """Execute command immediately on motors or servos."""
        cmd_type = cmd.get('type', '')

        if cmd_type == 'move':
            direction = cmd.get('direction', 'stop')
            self.direction = direction
            self.speed = cmd.get('speed', self.speed)
            logger.info(f"⚡ MOTOR ACTION: Move {direction} at {self.speed}%")
            self._apply_movement()

        elif cmd_type == 'speed':
            self.speed = cmd.get('value', 50)
            logger.info(f"⚡ MOTOR ACTION: Speed set to {self.speed}%")
            if self.direction != 'stop':
                self._apply_movement()

        elif cmd_type == 'joint':
            joint = cmd.get('joint', '')
            angle = float(cmd.get('angle', 0.0))
            logger.info(f"⚡ SERVO ACTION: Joint {joint} -> {angle}°")
            self.hw.set_servo_angle(joint, angle)

        elif cmd_type == 'stance':
            stance = cmd.get('stance', 'stand')
            logger.info(f"⚡ STANCE ACTION: Applying pose '{stance}'")
            if stance == 'stand':
                self.hw.set_servo_angle('LHip', 0)
                self.hw.set_servo_angle('RHip', 0)
                self.hw.set_servo_angle('LKnee', 0)
                self.hw.set_servo_angle('RKnee', 0)
            elif stance == 'crouch':
                self.hw.set_servo_angle('LHip', 30)
                self.hw.set_servo_angle('RHip', 30)
                self.hw.set_servo_angle('LKnee', -60)
                self.hw.set_servo_angle('RKnee', -60)
            elif stance == 'estop':
                self.hw.stop()
                self.direction = 'stop'

        elif cmd_type == 'control':
            mode = cmd.get('mode', 'manual')
            self.balance_mode = (mode == 'balance')
            if not self.balance_mode:
                self.hw.stop()
            logger.info(f"Control mode: {mode}")

    def _apply_movement(self):
        if self.direction == 'forward':
            self.hw.set_speeds(self.speed, self.speed)
        elif self.direction == 'backward':
            self.hw.set_speeds(-self.speed, -self.speed)
        elif self.direction == 'left':
            self.hw.set_speeds(-self.speed, self.speed)
        elif self.direction == 'right':
            self.hw.set_speeds(self.speed, -self.speed)
        else:
            self.hw.stop()

    def update_balance_loop(self, dt=0.02):
        self.pitch, self.pitch_rate = self.imu.read_pitch()

        if self.balance_mode:
            target_pitch = 0.0
            if self.direction == 'forward': target_pitch = -3.0
            elif self.direction == 'backward': target_pitch = 3.0

            error = target_pitch - self.pitch
            self.pid_integral += error * dt
            self.pid_integral = max(-50.0, min(50.0, self.pid_integral))
            derivative = (error - self.pid_last_error) / dt if dt > 0 else 0
            output = self.kp * error + self.ki * self.pid_integral + self.kd * derivative
            self.pid_last_error = error

            pwm = max(-100, min(100, output * 4.0))
            if self.direction == 'left':
                self.hw.set_speeds(pwm - 20, pwm + 20)
            elif self.direction == 'right':
                self.hw.set_speeds(pwm + 20, pwm - 20)
            else:
                self.hw.set_speeds(pwm, pwm)

    def get_telemetry(self):
        return {
            'pitch': round(self.pitch, 2),
            'pitchRate': round(self.pitch_rate, 2),
            'balanceMode': self.balance_mode,
            'direction': self.direction,
            'speed': self.speed,
            'isHardware': self.imu.connected or self.hw.active,
            'power': 85.0,
            'temp': 35.0,
            'timestamp': time.time()
        }


# ============ WEBSOCKET SYNC CLIENT ============
async def run_client_loop(rpi, server_ws_url="ws://localhost:8765"):
    """Connect to server.py as a live hardware bridge and execute button presses in real time."""
    logger.info(f"Connecting to Chintu Server at {server_ws_url}...")

    while True:
        try:
            async with websockets.connect(server_ws_url) as ws:
                logger.info("✅ Connected to Chintu WebSocket Server! Ready for button presses.")
                await ws.send(json.dumps({'type': 'handshake', 'client': 'rpi-hardware-node'}))

                async for message in ws:
                    try:
                        cmd = json.loads(message)
                        rpi.handle_command(cmd)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.warning(f"WebSocket disconnected ({e}). Retrying in 2 seconds...")
            await asyncio.sleep(2.0)


def main():
    parser = argparse.ArgumentParser(description="Chintu Raspberry Pi Direct Controller")
    parser.add_argument('--test-imu', action='store_true', help="Continuously print MPU6050 pitch data")
    parser.add_argument('--test-motors', action='store_true', help="Run a quick motor forward/reverse test")
    parser.add_argument('--client', action='store_true', help="Connect to server.py via WebSocket and execute UI button presses")
    parser.add_argument('--ws-url', default="ws://localhost:8765", help="Server WebSocket URL")
    args = parser.parse_args()

    rpi = ChintuRpi()

    if args.test_imu:
        logger.info("Starting MPU6050 Live Stream (Press Ctrl+C to stop)...")
        try:
            while True:
                pitch, rate = rpi.imu.read_pitch()
                print(f"\r[IMU] Pitch: {pitch:+.2f}° | Rate: {rate:+.2f}°/s | Connected: {rpi.imu.connected}", end="", flush=True)
                time.sleep(0.05)
        except KeyboardInterrupt:
            print("\nStopped.")
            return

    if args.test_motors:
        logger.info("Testing Motors: Forward 2 seconds...")
        rpi.hw.set_speeds(50, 50)
        time.sleep(2)
        logger.info("Testing Motors: Backward 2 seconds...")
        rpi.hw.set_speeds(-50, -50)
        time.sleep(2)
        rpi.hw.stop()
        logger.info("Motor test completed.")
        rpi.hw.cleanup()
        return

    if args.client:
        asyncio.run(run_client_loop(rpi, args.ws_url))
    else:
        logger.info("Chintu Raspberry Pi Daemon Ready.")
        logger.info("👉 Use 'python3 rpi_chintu.py --client' to link with web dashboard buttons")
        logger.info("👉 Or run 'python3 server.py --auto-serial' if using ESP32 via USB")


if __name__ == '__main__':
    main()

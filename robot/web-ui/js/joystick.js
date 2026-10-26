/**
 * Virtual Touch Joystick, HTML5 Gamepad API, and WASD Keyboard Input Processor.
 * Gated speed capping (0.15 m/s & 50% yaw) and stuck-key clearing on blur/visibility.
 */

import { CONFIG } from './config.js';
import { State } from './state.js';

class JoystickManager {
  constructor() {
    this.container = null;
    this.thumb = null;
    this.active = false;
    this.pointerId = null;

    this.maxRadius = 80; // px
    this.centerX = 0;
    this.centerY = 0;

    // Keyboard state
    this.keys = {
      KeyW: false, KeyS: false, KeyA: false, KeyD: false,
      ArrowUp: false, ArrowDown: false, ArrowLeft: false, ArrowRight: false
    };

    // Gamepad state
    this.gamepadIndex = null;
  }

  init() {
    this.container = document.getElementById('joystick-zone');
    this.thumb = document.getElementById('joystick-knob');

    this.initTouchEvents();
    this.initKeyboardEvents();
    this.initGamepadEvents();
    this.initFocusClearing();
    this.startPollLoop();
  }

  initTouchEvents() {
    if (!this.container || !this.thumb) return;

    const onStart = (e) => {
      this.active = true;
      this.pointerId = e.pointerId;
      if (this.container.setPointerCapture && e.pointerId) {
        try { this.container.setPointerCapture(e.pointerId); } catch (_) {}
      }
      const rect = this.container.getBoundingClientRect();
      this.centerX = rect.left + rect.width / 2;
      this.centerY = rect.top + rect.height / 2;
      this.handlePointer(e);
    };

    const onMove = (e) => {
      if (!this.active || e.pointerId !== this.pointerId) return;
      this.handlePointer(e);
    };

    const onEnd = (e) => {
      if (!this.active || (e && e.pointerId !== this.pointerId)) return;
      if (this.container.releasePointerCapture && this.pointerId) {
        try { this.container.releasePointerCapture(this.pointerId); } catch (_) {}
      }
      this.reset();
    };

    this.container.addEventListener('pointerdown', onStart);
    this.container.addEventListener('pointermove', onMove);
    this.container.addEventListener('pointerup', onEnd);
    this.container.addEventListener('pointercancel', (e) => {
      this.clearAllKeys();
      onEnd(e);
    });
  }

  handlePointer(e) {
    let dx = e.clientX - this.centerX;
    let dy = e.clientY - this.centerY;

    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist > this.maxRadius) {
      dx = (dx / dist) * this.maxRadius;
      dy = (dy / dist) * this.maxRadius;
    }

    this.thumb.style.transform = `translate(${dx}px, ${dy}px)`;

    // Raw normalized values: [-1.0, 1.0]
    const rawX = dx / this.maxRadius;
    const rawY = -dy / this.maxRadius;

    this.applyProcessedDrive(rawY, rawX);
  }

  applyProcessedDrive(rawFwd, rawTurn) {
    const deadzone = CONFIG.DRIVE.DEADZONE;
    const expo = CONFIG.DRIVE.EXPO_POWER;

    // Apply Deadzone + Exponential Curve for fine center control
    const processAxis = (val) => {
      const absVal = Math.abs(val);
      if (absVal < deadzone) return 0.0;
      const normalized = (absVal - deadzone) / (1.0 - deadzone);
      return Math.sign(val) * Math.pow(normalized, expo);
    };

    const curveFwd = processAxis(rawFwd);
    const curveTurn = processAxis(rawTurn);

    let speedLimit = State.get('speedLimitMps');
    let maxTurnRate = CONFIG.DRIVE.MAX_YAW_RATE_RAD_S;

    // Bench Gate Interlock: clamp speed to 0.15 m/s and yaw to 50% if Gates 1 & 2 not passed
    const isFreeRun = State.isFreeRunUnlocked();
    if (!isFreeRun) {
      speedLimit = Math.min(speedLimit, CONFIG.DRIVE.GATED_SPEED_LIMIT_MPS);
      maxTurnRate *= 0.50;
    }

    if (State.get('gentleMode')) {
      speedLimit *= CONFIG.DRIVE.GENTLE_MODE_MULTIPLIER;
      maxTurnRate *= CONFIG.DRIVE.GENTLE_MODE_MULTIPLIER;
    }

    State.set('linearX', curveFwd * speedLimit);
    State.set('angularZ', -curveTurn * maxTurnRate);
  }

  reset() {
    this.active = false;
    this.pointerId = null;
    if (this.thumb) {
      this.thumb.style.transform = 'translate(0px, 0px)';
    }
    this.applyProcessedDrive(0, 0);
  }

  clearAllKeys() {
    for (const k in this.keys) {
      this.keys[k] = false;
    }
    this.reset();
  }

  initFocusClearing() {
    window.addEventListener('blur', () => this.clearAllKeys());
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.clearAllKeys();
      }
    });
  }

  initKeyboardEvents() {
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.code in this.keys) {
        this.keys[e.code] = true;
        this.processKeyboard();
      }
    });

    window.addEventListener('keyup', (e) => {
      if (e.code in this.keys) {
        this.keys[e.code] = false;
        this.processKeyboard();
      }
    });
  }

  processKeyboard() {
    if (this.active) return; // Touch joystick takes precedence

    let fwd = 0;
    let turn = 0;

    if (this.keys.KeyW || this.keys.ArrowUp) fwd += 1;
    if (this.keys.KeyS || this.keys.ArrowDown) fwd -= 1;
    if (this.keys.KeyA || this.keys.ArrowLeft) turn -= 1;
    if (this.keys.KeyD || this.keys.ArrowRight) turn += 1;

    this.applyProcessedDrive(fwd, turn);
  }

  initGamepadEvents() {
    window.addEventListener('gamepadconnected', (e) => {
      this.gamepadIndex = e.gamepad.index;
      const badge = document.getElementById('gamepad-badge');
      if (badge) badge.style.display = 'block';
      State.addLog('INPUT', `Gamepad connected: ${e.gamepad.id}`);
    });

    window.addEventListener('gamepaddisconnected', (e) => {
      if (this.gamepadIndex === e.gamepad.index) {
        this.gamepadIndex = null;
        const badge = document.getElementById('gamepad-badge');
        if (badge) badge.style.display = 'none';
        State.addLog('INPUT', 'Gamepad disconnected.');
        this.reset();
      }
    });
  }

  startPollLoop() {
    const poll = () => {
      if (this.gamepadIndex !== null && !this.active) {
        const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
        const gp = gamepads[this.gamepadIndex];
        if (gp) {
          // Standard Gamepad Mapping: Left Stick Y = Fwd/Rev, Right Stick X = Yaw
          const fwd = -gp.axes[1];
          const turn = gp.axes[2] !== undefined && Math.abs(gp.axes[2]) > 0.05 ? gp.axes[2] : gp.axes[0];
          this.applyProcessedDrive(fwd, turn);
        }
      }
      requestAnimationFrame(poll);
    };
    requestAnimationFrame(poll);
  }
}

export const Joystick = new JoystickManager();

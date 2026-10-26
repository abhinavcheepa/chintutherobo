/**
 * WebSocket API Client, Adaptive Rate Limiter & Telemetry Ingestion.
 * Fail-closed stale detection, automatic wss:// on HTTPS, and persistent E-STOP retries.
 */

import { CONFIG } from './config.js';
import { State } from './state.js';

class ApiClient {
  constructor() {
    this.ws = null;
    this.reconnectTimer = null;
    this.reconnectAttempts = 0;
    this.pingTimer = null;
    this.commandTimer = null;

    this.lastSentCommand = null;
    this.lastCommandTime = 0;
    this.commandId = 0;
  }

  async connect() {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    if (!CONFIG.AUTH_TOKEN) {
      State.set('connStatus', 'AUTH_REQUIRED');
      const authModal = document.getElementById('auth-modal');
      if (authModal) authModal.classList.remove('hidden');
      return;
    }

    const host = window.location.hostname || '127.0.0.1';
    const port = window.location.port || CONFIG.WS_PORT;
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const httpProtocol = window.location.protocol === 'https:' ? 'https:' : 'http:';

    State.set('connStatus', 'CONNECTING');

    // 1. Fetch single-use ticket via POST /api/ws-ticket
    let ticket = null;
    try {
      const res = await fetch(`${httpProtocol}//${host}:${port}/api/ws-ticket`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${CONFIG.AUTH_TOKEN}`,
          'Content-Type': 'application/json'
        }
      });
      if (res.status === 401) {
        State.set('connStatus', 'AUTH_FAILED');
        State.addLog('NET', 'Authentication failed: invalid supervisor token.');
        const authModal = document.getElementById('auth-modal');
        if (authModal) authModal.classList.remove('hidden');
        return;
      }
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: Failed to fetch WebSocket ticket`);
      }
      const data = await res.json();
      ticket = data.ticket;
    } catch (err) {
      console.warn('Failed to obtain WebSocket ticket:', err);
      State.set('connStatus', 'DISCONNECTED');
      this.scheduleReconnect();
      return;
    }

    const wsUrl = `${wsProtocol}//${host}:${port}/ws?ticket=${encodeURIComponent(ticket)}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        State.set('connected', true);
        State.set('connStatus', 'ONLINE');
        State.addLog('NET', `Connected to supervisor via ${protocol}//${host}:${port}`);

        // If an E-STOP was triggered while offline, deliver it immediately upon link restore
        if (State.get('estopPending') || State.get('estopActive')) {
          this.sendEstop('RECONNECTED_PENDING_ESTOP');
        }

        this.startPingLoop();
        this.startCommandLoop();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        } catch (err) {
          console.error('Failed to parse incoming WS message:', err);
        }
      };

      this.ws.onclose = () => {
        this.cleanup();
        State.set('connected', false);
        State.set('connStatus', 'DISCONNECTED');
        State.set('isController', false);
        State.addLog('NET', 'WebSocket disconnected. Scheduling reconnect...');
        this.scheduleReconnect();
      };

      this.ws.onerror = (err) => {
        console.warn('WebSocket encountered error:', err);
        this.ws.close();
      };
    } catch (e) {
      console.error('WebSocket connection failure:', e);
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    if (this.reconnectTimer) return;
    const delay = Math.min(CONFIG.MAX_RECONNECT_DELAY_MS, 1000 * Math.pow(1.4, this.reconnectAttempts));
    this.reconnectAttempts++;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  startPingLoop() {
    clearInterval(this.pingTimer);
    this.pingTimer = setInterval(() => {
      if (this.isOpen()) {
        this.send({ type: 'ping', client_time: performance.now() });
      }
    }, 2000);
  }

  cleanup() {
    clearInterval(this.pingTimer);
    clearInterval(this.commandTimer);
  }

  isOpen() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  send(data) {
    if (this.isOpen()) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  handleMessage(msg) {
    if (msg.type === 'pong') {
      const rtt = Math.round(performance.now() - msg.client_time);
      State.set('rttMs', rtt);
      return;
    }

    if (msg.type === 'connection_ack') {
      State.set('isController', Boolean(msg.is_controller));
      State.addLog('NET', `Client role: ${msg.is_controller ? 'PRIMARY CONTROLLER' : 'READ-ONLY OBSERVER'}`);
      return;
    }

    if (msg.type === 'estop_ack') {
      State.set('estopPending', false);
      State.addLog('SAFETY', 'E-STOP confirmed delivered by supervisor.');
      return;
    }

    if (msg.type === 'error') {
      State.addLog('WARN', `Supervisor: ${msg.message}`);
      return;
    }

    if (msg.type === 'telemetry') {
      State.set('lastRxTimestamp', performance.now());

      // Fail-closed packet freshness handling: never default to 0 if missing/null!
      const rawAge = msg.diagnostics?.packet_age_ms;
      const packetAge = (typeof rawAge === 'number' && !isNaN(rawAge)) ? rawAge : 9999;
      State.set('packetAgeMs', packetAge);

      // State Machine
      State.set('robotState', msg.state);
      State.set('stateCode', msg.state_code);
      State.set('errorFlags', msg.diagnostics?.error_flags ?? 0);
      State.set('errorDesc', msg.diagnostics?.error_desc ?? 'NOMINAL');

      // Reset E-STOP latch ONLY when robot confirms safe DISARMED state and cleared flags
      if (msg.state === 'DISARMED' && (msg.diagnostics?.error_flags ?? 0) === 0) {
        if (State.get('estopActive') && !State.get('estopPending')) {
          State.set('estopActive', false);
          State.addLog('SAFETY', 'Robot confirmed DISARMED with zero faults; E-STOP latch reset.');
        }
      }

      // Power
      const volts = msg.power?.battery_voltage ?? 0.0;
      State.set('batteryVoltage', volts);
      State.set('vBattMv', msg.power?.v_batt_mv ?? Math.round(volts * 1000));

      let bStatus = 'OK';
      if (volts <= CONFIG.BATTERY.CRITICAL_VOLTS) bStatus = 'CRITICAL';
      else if (volts <= CONFIG.BATTERY.WARN_VOLTS) bStatus = 'WARN';
      State.set('batteryStatus', bStatus);

      const pct = Math.max(0, Math.min(100, Math.round(((volts - CONFIG.BATTERY.EMPTY_VOLTS) / (CONFIG.BATTERY.FULL_VOLTS - CONFIG.BATTERY.EMPTY_VOLTS)) * 100)));
      State.set('batteryPercent', pct);

      // Pose & Actuators
      if (msg.pose) {
        State.set('pitch', msg.pose.pitch);
        State.set('pitchRate', msg.pose.pitch_rate);
        State.set('roll', msg.pose.roll);
        State.set('yawRate', msg.pose.yaw_rate);
      }

      if (msg.wheels) {
        State.set('wheelPosL', msg.wheels.pos_left);
        State.set('wheelPosR', msg.wheels.pos_right);
        State.set('wheelVelL', msg.wheels.vel_left);
        State.set('wheelVelR', msg.wheels.vel_right);
      }

      if (msg.legs) {
        State.set('legHeightL', msg.legs.height_left);
        State.set('legHeightR', msg.legs.height_right);
      }

      // Supervisor Diagnostics
      if (msg.diagnostics) {
        State.set('loopJitterUs', msg.diagnostics.loop_jitter_us);
        State.set('lastCmdId', msg.diagnostics.last_cmd_id);
      }
      if (msg.system) {
        State.set('cpuTempC', msg.system.cpu_temp_c);
      }
    }
  }

  startCommandLoop() {
    clearInterval(this.commandTimer);
    const loopIntervalMs = Math.round(1000 / CONFIG.COMMAND_RATE_HZ);

    this.commandTimer = setInterval(() => {
      this.dispatchMotionTick();
    }, loopIntervalMs);
  }

  dispatchMotionTick() {
    if (!this.isOpen()) return;

    // Do NOT stream motion commands if in E-STOP, FAULT, or DISARMED
    const rState = State.get('robotState');
    const isEStopped = State.get('estopActive');
    const browserAge = performance.now() - (State.get('lastRxTimestamp') || 0);
    const packetAge = State.get('packetAgeMs');

    // Fail-closed stale check
    const isStale = browserAge > CONFIG.STALE_TELEMETRY_THRESHOLD_MS || packetAge > CONFIG.STALE_TELEMETRY_THRESHOLD_MS;

    if (isEStopped || rState !== 'ARMED' || isStale) {
      return;
    }

    const linearX = State.get('linearX');
    const angularZ = State.get('angularZ');
    const height = State.get('targetHeight');
    const rollTrim = State.get('rollTrim');
    const balanceEnable = State.get('balanceEnable');
    const freeRunUnlocked = State.isFreeRunUnlocked();

    const isStationary = (Math.abs(linearX) < 0.001 && Math.abs(angularZ) < 0.001);
    const now = performance.now();

    // While ARMED and stationary, keepalive must be sent every <= 150 ms (100 ms = 10 Hz)
    const keepaliveIntervalMs = Math.round(1000 / CONFIG.KEEPALIVE_RATE_HZ);
    if (isStationary && (now - this.lastCommandTime) < keepaliveIntervalMs) {
      return;
    }

    this.commandId = (this.commandId + 1) & 0xFFFF;
    const cmdPayload = {
      type: 'command',
      linear_x: Number(linearX.toFixed(3)),
      angular_z: Number(angularZ.toFixed(3)),
      leg_height_l: Math.round(height),
      leg_height_r: Math.round(height),
      roll_trim: Number(rollTrim.toFixed(3)),
      balance_enable: Boolean(balanceEnable),
      free_run_unlocked: Boolean(freeRunUnlocked),
      command_id: this.commandId
    };

    this.send(cmdPayload);
    this.lastCommandTime = now;
  }

  sendArmState(stateName) {
    State.addLog('STATE', `Requesting state transition to: ${stateName}`);
    this.send({ type: 'arm_state', state: stateName });
  }

  sendEstop(reason = 'USER_BUTTON') {
    State.set('estopActive', true);
    State.addLog('SAFETY', `E-STOP TRIGGERED! Reason: ${reason}`);

    const delivered = this.send({ type: 'estop', reason });
    if (!delivered) {
      State.set('estopPending', true);
      State.addLog('WARN', 'E-STOP NOT DELIVERED: WebSocket disconnected. Retrying on reconnect...');
    } else {
      State.set('estopPending', false);
    }
  }

  sendPidConfig(controllerId, kp, ki, kd, k_ff, saveToEeprom = false) {
    State.addLog('TUNE', `Sending PID gains for controller #${controllerId} (EEPROM=${saveToEeprom})`);
    this.send({
      type: 'pid_set',
      controller_id: controllerId,
      save_to_eeprom: saveToEeprom,
      kp, ki, kd, k_ff
    });
  }

  sendSaveEeprom() {
    State.addLog('TUNE', 'Committing active PID gains to Mega EEPROM');
    this.send({ type: 'save_eeprom' });
  }
}

export const Api = new ApiClient();

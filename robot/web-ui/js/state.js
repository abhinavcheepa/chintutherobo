/**
 * Reactive Central State Store & Event Bus.
 */

import { CONFIG } from './config.js';

class StateStore {
  constructor() {
    this.listeners = new Map();

    // Persistent Bench Gates
    const savedGates = JSON.parse(localStorage.getItem('chintu_bench_gates') || '{}');
    // Persistent E-Stop (prevents resetting E-Stop via page refresh alone)
    const savedEstop = localStorage.getItem('chintu_estop_active') === 'true';

    this.data = {
      // Connection & Security
      connected: false,
      connStatus: 'DISCONNECTED', // 'ONLINE', 'CONNECTING', 'DISCONNECTED', 'STALE'
      isController: false,        // True if this client holds primary controller lock
      rttMs: 0,
      packetAgeMs: 9999,
      lastRxTimestamp: 0,
      isSecureContext: window.isSecureContext || false,

      // Robot State Machine
      robotState: 'DISARMED',
      stateCode: 0,
      errorFlags: 0,
      errorDesc: 'INITIALIZING',

      // Power
      batteryVoltage: 0.0,
      vBattMv: 0,
      batteryStatus: 'WARN', // 'OK', 'WARN', 'CRITICAL'
      batteryPercent: 0,

      // Pose & Dynamics
      pitch: 0.0,
      pitchRate: 0.0,
      roll: 0.0,
      yawRate: 0.0,

      // Actuator Telemetry
      wheelPosL: 0,
      wheelPosR: 0,
      wheelVelL: 0,
      wheelVelR: 0,
      legHeightL: CONFIG.LEGS.NOMINAL_HEIGHT_MM,
      legHeightR: CONFIG.LEGS.NOMINAL_HEIGHT_MM,

      // Supervisor Diagnostics
      loopJitterUs: 0,
      cpuTempC: 0.0,
      lastCmdId: 0,

      // Drive Setpoints
      linearX: 0.0,
      angularZ: 0.0,
      targetHeight: CONFIG.LEGS.NOMINAL_HEIGHT_MM,
      rollTrim: 0.0,
      speedLimitMps: CONFIG.DRIVE.DEFAULT_SPEED_LIMIT_MPS,
      gentleMode: false,
      balanceEnable: true,
      estopActive: savedEstop,
      estopPending: false, // True if E-Stop queued while offline
      activeTab: 'drive',

      // Bench Gate Checklist Tracker
      gates: {
        gate1_bench_stand: savedGates.gate1_bench_stand || false,
        gate2_tethered: savedGates.gate2_tethered || false,
        gate3_free_run: savedGates.gate3_free_run || false
      },

      // Flight event log (circular buffer)
      eventLogs: []
    };
  }

  get(key) {
    return this.data[key];
  }

  set(key, value) {
    if (this.data[key] === value) return;
    const oldVal = this.data[key];
    this.data[key] = value;

    if (key === 'estopActive') {
      localStorage.setItem('chintu_estop_active', value ? 'true' : 'false');
    }

    this._emit(key, value, oldVal);
  }

  update(patch) {
    for (const [k, v] of Object.entries(patch)) {
      this.set(k, v);
    }
  }

  on(key, callback) {
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key).add(callback);
    return () => this.listeners.get(key).delete(callback);
  }

  _emit(key, value, oldValue) {
    if (this.listeners.has(key)) {
      for (const cb of this.listeners.get(key)) {
        try {
          cb(value, oldValue);
        } catch (err) {
          console.error(`Error in state listener for [${key}]:`, err);
        }
      }
    }
  }

  addLog(level, message) {
    const entry = {
      timestamp: new Date().toLocaleTimeString(),
      level: level.toUpperCase(),
      message
    };
    this.data.eventLogs.unshift(entry);
    if (this.data.eventLogs.length > 200) {
      this.data.eventLogs.pop();
    }
    this._emit('eventLogs', this.data.eventLogs);
  }

  saveGateChecklist(gateKey, checked) {
    this.data.gates[gateKey] = checked;
    localStorage.setItem('chintu_bench_gates', JSON.stringify(this.data.gates));
    this._emit('gates', this.data.gates);
    this.addLog('GATE', `Checklist updated: ${gateKey} = ${checked}`);
  }

  isFreeRunUnlocked() {
    return Boolean(this.data.gates.gate1_bench_stand && this.data.gates.gate2_tethered);
  }
}

export const State = new StateStore();

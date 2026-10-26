/**
 * PID Parameter Tuning Drawer with Presets, Revert, and Safety Interlocks.
 */

import { State } from './state.js';
import { Api } from './api.js';

class TuningController {
  constructor() {
    this.activeControllerId = 0; // 0: Pitch, 1: Vel, 2: Yaw

    // Default presets
    this.defaultPresets = {
      default_bench: {
        name: 'Default Bench Stand',
        0: { kp: 30.0, ki: 0.15, kd: 1.45, kff: 0.05 },
        1: { kp: 0.012, ki: 0.001, kd: 0.001, kff: 0.0 },
        2: { kp: 1.5, ki: 0.0, kd: 0.08, kff: 0.0 }
      },
      aggressive_ground: {
        name: 'Aggressive Ground Run',
        0: { kp: 38.0, ki: 0.25, kd: 1.85, kff: 0.08 },
        1: { kp: 0.018, ki: 0.002, kd: 0.002, kff: 0.0 },
        2: { kp: 2.0, ki: 0.01, kd: 0.12, kff: 0.0 }
      },
      gentle_crouch: {
        name: 'Gentle Low-Height Crouch',
        0: { kp: 24.0, ki: 0.10, kd: 1.10, kff: 0.02 },
        1: { kp: 0.008, ki: 0.001, kd: 0.001, kff: 0.0 },
        2: { kp: 1.2, ki: 0.0, kd: 0.05, kff: 0.0 }
      }
    };

    this.presets = JSON.parse(localStorage.getItem('chintu_tuning_presets') || JSON.stringify(this.defaultPresets));
    this.historyStack = [];
  }

  init() {
    this.bindDomEvents();
    this.loadActiveControllerIntoUi();
  }

  bindDomEvents() {
    const selectCtrl = document.getElementById('tune-controller-select');
    if (selectCtrl) {
      selectCtrl.addEventListener('change', (e) => {
        this.activeControllerId = parseInt(e.target.value, 10);
        this.loadActiveControllerIntoUi();
      });
    }

    const selectPreset = document.getElementById('tune-preset-select');
    if (selectPreset) {
      this.populatePresetDropdown(selectPreset);
      selectPreset.addEventListener('change', (e) => {
        this.applyPreset(e.target.value);
      });
    }

    // Sync Sliders <-> Numeric Inputs
    const pairs = [
      ['tune-kp-slider', 'tune-kp-num'],
      ['tune-ki-slider', 'tune-ki-num'],
      ['tune-kd-slider', 'tune-kd-num'],
      ['tune-kff-slider', 'tune-kff-num']
    ];

    pairs.forEach(([sliderId, numId]) => {
      const slider = document.getElementById(sliderId);
      const num = document.getElementById(numId);
      if (slider && num) {
        slider.addEventListener('input', () => { num.value = slider.value; });
        num.addEventListener('input', () => { slider.value = num.value; });
      }
    });

    // Send Button with ARMED Safety Confirmation
    const btnSend = document.getElementById('btn-tune-send');
    if (btnSend) {
      btnSend.addEventListener('click', () => {
        this.requestSendGains(false);
      });
    }

    // Burn to EEPROM
    const btnBurn = document.getElementById('btn-tune-burn');
    if (btnBurn) {
      btnBurn.addEventListener('click', () => {
        this.requestSendGains(true);
      });
    }

    // Revert Last
    const btnRevert = document.getElementById('btn-tune-revert');
    if (btnRevert) {
      btnRevert.addEventListener('click', () => {
        this.revertLast();
      });
    }
  }

  populatePresetDropdown(selectEl) {
    selectEl.innerHTML = '';
    for (const [key, p] of Object.entries(this.presets)) {
      const opt = document.createElement('option');
      opt.value = key;
      opt.textContent = p.name;
      selectEl.appendChild(opt);
    }
  }

  getCurrentFormGains() {
    return {
      kp: parseFloat(document.getElementById('tune-kp-num')?.value || 30.0),
      ki: parseFloat(document.getElementById('tune-ki-num')?.value || 0.15),
      kd: parseFloat(document.getElementById('tune-kd-num')?.value || 1.45),
      kff: parseFloat(document.getElementById('tune-kff-num')?.value || 0.05)
    };
  }

  setFormGains(g) {
    const setVal = (sliderId, numId, val) => {
      const s = document.getElementById(sliderId);
      const n = document.getElementById(numId);
      if (s) s.value = val;
      if (n) n.value = val;
    };
    setVal('tune-kp-slider', 'tune-kp-num', g.kp);
    setVal('tune-ki-slider', 'tune-ki-num', g.ki);
    setVal('tune-kd-slider', 'tune-kd-num', g.kd);
    setVal('tune-kff-slider', 'tune-kff-num', g.kff);
  }

  loadActiveControllerIntoUi() {
    const currentPreset = this.presets.default_bench[this.activeControllerId];
    if (currentPreset) {
      this.setFormGains(currentPreset);
    }
  }

  applyPreset(presetKey) {
    const p = this.presets[presetKey];
    if (!p) return;
    const g = p[this.activeControllerId];
    if (g) {
      this.setFormGains(g);
      State.addLog('TUNE', `Applied preset: ${p.name}`);
    }
  }

  requestSendGains(burnEeprom) {
    const isArmed = State.get('robotState') === 'ARMED';

    if (isArmed) {
      const ok = confirm('⚠️ CRITICAL SAFETY WARNING:\n\nThe robot is currently ARMED! Changing PID gains while balancing may induce violent motor oscillation or loss of balance.\n\nAre you sure you want to apply gains while ARMED?');
      if (!ok) return;
    }

    const g = this.getCurrentFormGains();
    this.historyStack.push({ ...g, controllerId: this.activeControllerId });

    Api.sendPidConfig(this.activeControllerId, g.kp, g.ki, g.kd, g.kff, burnEeprom);

    // Visual button feedback
    const btn = burnEeprom ? document.getElementById('btn-tune-burn') : document.getElementById('btn-tune-send');
    if (btn) {
      const origText = btn.textContent;
      btn.textContent = 'TRANSMITTED ✓';
      btn.classList.add('btn-success');
      setTimeout(() => {
        btn.textContent = origText;
        btn.classList.remove('btn-success');
      }, 1200);
    }
  }

  revertLast() {
    if (this.historyStack.length === 0) {
      alert('No previous gain history available to revert.');
      return;
    }
    const prev = this.historyStack.pop();
    this.setFormGains(prev);
    Api.sendPidConfig(prev.controllerId, prev.kp, prev.ki, prev.kd, prev.kff, false);
    State.addLog('TUNE', 'Reverted to prior gain setpoint.');
  }
}

export const Tune = new TuningController();

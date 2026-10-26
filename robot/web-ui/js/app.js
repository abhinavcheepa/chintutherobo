/**
 * Master Application Controller & Navigation Coordinator for Chintu Biped HUD.
 */

import { CONFIG } from './config.js';
import { State } from './state.js';
import { Api } from './api.js';
import { Safety } from './safety.js';
import { Joystick } from './joystick.js';
import { Charts } from './charts.js';
import { View3D } from './view3d.js';
import { Tune } from './tune.js';
import { Calibrate } from './calibrate.js';

class ApplicationController {
  constructor() {
    this.activeTab = 'drive';
    this.swRegistration = null;
  }

  init() {
    console.log('Initializing Chintu Biped Field HUD...');

    // 1. Initialize Subsystem Modules
    Safety.init();
    Joystick.init();
    Charts.init();
    View3D.init();
    Tune.init();
    Calibrate.init();

    // 2. Bind Status Bar & Reactive State
    this.bindStatusBar();

    // 3. Bind Tab Navigation
    this.bindTabs();

    // 4. Bind Driving Screen Sliders & Toggles
    this.bindDriveControls();

    // 5. Bind Bench Gate Checklist
    this.bindBenchGates();

    // 6. Bind Event Logs Tab
    this.bindLogs();

    // 7. Bind Settings Tab & Auth Token
    this.bindSettings();

    // 8. Bind E-Stop and Disarm Actions
    this.bindSafetyButtons();

    // 9. Connect WebSocket to Supervisor
    Api.connect();

    // 10. Register Offline PWA Service Worker with Update Prompt
    this.registerServiceWorker();
  }

  bindStatusBar() {
    const connBadge = document.getElementById('conn-badge');
    const stateBadge = document.getElementById('robot-state-chip');
    const battVolts = document.getElementById('stat-batt-volts');
    const battGauge = document.getElementById('stat-batt-bar');
    const rttEl = document.getElementById('stat-rtt');
    const jitterEl = document.getElementById('stat-jitter');
    const cpuTempEl = document.getElementById('stat-cpu-temp');
    const roleChip = document.getElementById('client-role-chip');

    // Connection Status
    State.on('connStatus', (status) => {
      if (!connBadge) return;
      connBadge.textContent = status;
      connBadge.className = `badge badge-${status.toLowerCase()}`;
    });

    // Client Role (Primary Controller vs Observer)
    State.on('isController', (isCtrl) => {
      if (!roleChip) return;
      roleChip.textContent = isCtrl ? 'CONTROLLER' : 'OBSERVER';
      roleChip.className = isCtrl ? 'badge badge-online' : 'badge badge-connecting';
    });

    // Robot State Machine Chip
    State.on('robotState', (s) => {
      if (!stateBadge) return;
      stateBadge.textContent = s;
      stateBadge.className = `state-chip state-${s.toLowerCase()}`;
    });

    // Battery Voltage & Threshold Coloring
    State.on('batteryVoltage', (volts) => {
      if (battVolts) battVolts.textContent = `${volts.toFixed(2)} V`;
      if (battGauge) {
        const pct = State.get('batteryPercent');
        battGauge.style.width = `${pct}%`;

        battGauge.classList.remove('gauge-green', 'gauge-amber', 'gauge-red');
        if (volts >= CONFIG.BATTERY.ARM_MIN_VOLTS) {
          battGauge.classList.add('gauge-green');
        } else if (volts >= CONFIG.BATTERY.WARN_VOLTS) {
          battGauge.classList.add('gauge-amber');
        } else {
          battGauge.classList.add('gauge-red');
        }
      }
    });

    // RTT
    State.on('rttMs', (rtt) => {
      if (rttEl) rttEl.textContent = `${rtt} ms`;
    });

    // Loop Jitter
    State.on('loopJitterUs', (jitter) => {
      if (jitterEl) jitterEl.textContent = `${jitter} µs`;
    });

    // Pi CPU Temp
    State.on('cpuTempC', (temp) => {
      if (cpuTempEl) cpuTempEl.textContent = `${temp > 0 ? temp.toFixed(1) : '--'} °C`;
    });
  }

  bindTabs() {
    const tabButtons = document.querySelectorAll('.nav-tab-btn');
    tabButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const tabId = e.currentTarget.dataset.tab;
        this.switchTab(tabId);
      });
    });
  }

  switchTab(tabId) {
    this.activeTab = tabId;
    State.set('activeTab', tabId);

    // Update Tab Buttons
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });

    // Update Tab Panels
    document.querySelectorAll('.tab-panel').forEach(panel => {
      panel.classList.toggle('hidden', panel.id !== `tab-${tabId}`);
    });

    State.addLog('UI', `Switched to tab: ${tabId.toUpperCase()}`);
  }

  bindDriveControls() {
    // Leg Height Slider (Nominal 135mm based on IK derivation)
    const sliderHeight = document.getElementById('slider-height');
    const valHeight = document.getElementById('val-height');
    if (sliderHeight && valHeight) {
      sliderHeight.min = CONFIG.LEGS.MIN_HEIGHT_MM;
      sliderHeight.max = CONFIG.LEGS.MAX_HEIGHT_MM;
      sliderHeight.value = CONFIG.LEGS.NOMINAL_HEIGHT_MM;
      valHeight.textContent = `${sliderHeight.value} mm`;

      sliderHeight.addEventListener('input', (e) => {
        const h = parseInt(e.target.value, 10);
        valHeight.textContent = `${h} mm`;
        State.set('targetHeight', h);
      });
    }

    // Pitch Trim Slider
    const sliderTrim = document.getElementById('slider-pitch-trim');
    const valTrim = document.getElementById('val-pitch-trim');
    if (sliderTrim && valTrim) {
      sliderTrim.addEventListener('input', (e) => {
        const trim = parseFloat(e.target.value);
        valTrim.textContent = `${trim >= 0 ? '+' : ''}${trim.toFixed(1)}°`;
        State.set('rollTrim', trim);
      });
    }

    // Speed Limit Slider
    const sliderSpeed = document.getElementById('slider-speed-limit');
    const valSpeed = document.getElementById('val-speed-limit');
    if (sliderSpeed && valSpeed) {
      sliderSpeed.value = CONFIG.DRIVE.DEFAULT_SPEED_LIMIT_MPS;
      valSpeed.textContent = `${CONFIG.DRIVE.DEFAULT_SPEED_LIMIT_MPS.toFixed(2)} m/s`;

      sliderSpeed.addEventListener('input', (e) => {
        let speed = parseFloat(e.target.value);

        // Bench Gate Interlock: clamp speed if Gates 1 & 2 not passed
        if (!State.isFreeRunUnlocked() && speed > CONFIG.DRIVE.GATED_SPEED_LIMIT_MPS) {
          speed = CONFIG.DRIVE.GATED_SPEED_LIMIT_MPS;
          sliderSpeed.value = CONFIG.DRIVE.GATED_SPEED_LIMIT_MPS;
          alert('Gate 1 & Gate 2 must be completed in Bench Gates tab before raising speed above 0.15 m/s!');
        }

        valSpeed.textContent = `${speed.toFixed(2)} m/s`;
        State.set('speedLimitMps', speed);
      });
    }

    // Gentle Mode Toggle
    const checkGentle = document.getElementById('toggle-gentle-mode');
    if (checkGentle) {
      checkGentle.addEventListener('change', (e) => {
        State.set('gentleMode', e.target.checked);
        State.addLog('DRIVE', `Gentle Mode: ${e.target.checked ? 'ENABLED' : 'DISABLED'}`);
      });
    }

    // Balance Enable Toggle
    const checkBalance = document.getElementById('toggle-balance-enable');
    if (checkBalance) {
      checkBalance.addEventListener('change', (e) => {
        State.set('balanceEnable', e.target.checked);
        State.addLog('DRIVE', `Balance Loop: ${e.target.checked ? 'ENABLED' : 'DISABLED'}`);
      });
    }

    // Live Attitude HUD on Drive Screen
    const attitudePitch = document.getElementById('drive-live-pitch');
    const attitudeRoll = document.getElementById('drive-live-roll');
    State.on('pitch', (p) => {
      if (attitudePitch) attitudePitch.textContent = `${p.toFixed(1)}°`;
    });
    State.on('roll', (r) => {
      if (attitudeRoll) attitudeRoll.textContent = `${r.toFixed(1)}°`;
    });
  }

  bindBenchGates() {
    const gate1 = document.getElementById('chk-gate1');
    const gate2 = document.getElementById('chk-gate2');
    const gate3 = document.getElementById('chk-gate3');
    const statusMsg = document.getElementById('gate-lock-status');

    const updateGateStatus = () => {
      const unlocked = State.isFreeRunUnlocked();
      if (statusMsg) {
        if (unlocked) {
          statusMsg.textContent = '✓ FREE-RUN UNLOCKED (Gate 1 & 2 Completed)';
          statusMsg.className = 'gate-banner gate-banner-unlocked';
        } else {
          statusMsg.textContent = '🔒 FREE-RUN LOCKED (Capped at 0.15 m/s & 50% turn until Gate 1 & 2 are checked)';
          statusMsg.className = 'gate-banner gate-banner-locked';
        }
      }
    };

    if (gate1) {
      gate1.checked = State.get('gates').gate1_bench_stand;
      gate1.addEventListener('change', (e) => {
        State.saveGateChecklist('gate1_bench_stand', e.target.checked);
        updateGateStatus();
      });
    }

    if (gate2) {
      gate2.checked = State.get('gates').gate2_tethered;
      gate2.addEventListener('change', (e) => {
        State.saveGateChecklist('gate2_tethered', e.target.checked);
        updateGateStatus();
      });
    }

    if (gate3) {
      gate3.checked = State.get('gates').gate3_free_run;
      gate3.addEventListener('change', (e) => {
        State.saveGateChecklist('gate3_free_run', e.target.checked);
        updateGateStatus();
      });
    }

    updateGateStatus();
  }

  bindLogs() {
    const logContainer = document.getElementById('log-stream-list');
    const btnClearLogs = document.getElementById('btn-clear-logs');
    const btnDownloadLogs = document.getElementById('btn-download-logs');

    State.on('eventLogs', (logs) => {
      if (!logContainer) return;
      logContainer.innerHTML = '';
      logs.slice(0, 50).forEach(item => {
        const row = document.createElement('div');
        row.className = `log-row log-${item.level.toLowerCase()}`;

        const timeSpan = document.createElement('span');
        timeSpan.className = 'log-time';
        timeSpan.textContent = item.timestamp;

        const levelSpan = document.createElement('span');
        levelSpan.className = 'log-level';
        levelSpan.textContent = `[${item.level}]`;

        const msgSpan = document.createElement('span');
        msgSpan.className = 'log-msg';
        msgSpan.textContent = item.message;

        row.appendChild(timeSpan);
        row.appendChild(levelSpan);
        row.appendChild(msgSpan);
        logContainer.appendChild(row);
      });
    });

    if (btnClearLogs) {
      btnClearLogs.addEventListener('click', () => {
        State.set('eventLogs', []);
      });
    }

    if (btnDownloadLogs) {
      btnDownloadLogs.addEventListener('click', () => {
        const logs = State.get('eventLogs');
        const text = logs.map(l => `${l.timestamp} [${l.level}] ${l.message}`).join('\n');
        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chintu_flight_log_${Date.now()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    }
  }

  bindSettings() {
    const tokenInput = document.getElementById('settings-auth-token');
    const btnSaveToken = document.getElementById('btn-save-token');

    if (tokenInput) {
      tokenInput.value = CONFIG.AUTH_TOKEN;
    }

    if (btnSaveToken && tokenInput) {
      btnSaveToken.addEventListener('click', () => {
        const val = tokenInput.value.trim();
        CONFIG.AUTH_TOKEN = val;
        State.addLog('CONFIG', 'Updated authentication token in browser storage.');
        alert('Authentication token saved. Reconnecting WebSocket...');
        if (Api.ws) Api.ws.close();
      });
    }
  }

  bindSafetyButtons() {
    // Persistent E-Stop Button
    const btnEstop = document.getElementById('btn-estop');
    if (btnEstop) {
      btnEstop.addEventListener('click', () => {
        Safety.playTone(CONFIG.AUDIO.BEEP_ESTOP_HZ, 400, 'sawtooth');
        Safety.vibrate([200, 100, 200, 100, 400]);
        Api.sendEstop('USER_PANIC_ESTOP');
      });
    }

    // Disarm Button (visible when ARMED)
    const btnDisarm = document.getElementById('btn-disarm');
    if (btnDisarm) {
      btnDisarm.addEventListener('click', () => {
        Safety.playTone(CONFIG.AUDIO.BEEP_DISARM_HZ, 200, 'sine');
        Safety.vibrate(80);
        Api.sendArmState('DISARMED');
      });
    }

    // Clear Fault Button
    const btnClearFault = document.getElementById('btn-clear-fault');
    if (btnClearFault) {
      btnClearFault.addEventListener('click', () => {
        State.set('estopActive', false);
        State.set('estopPending', false);
        Api.sendArmState('CLEAR_FAULT');
      });
    }
  }

  registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('./sw.js')
          .then((reg) => {
            this.swRegistration = reg;
            console.log('Service Worker registered with scope:', reg.scope);

            reg.addEventListener('updatefound', () => {
              const newWorker = reg.installing;
              newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                  this.showUpdateToast();
                }
              });
            });
          })
          .catch((err) => console.warn('Service Worker registration failed:', err));

        navigator.serviceWorker.addEventListener('controllerchange', () => {
          window.location.reload();
        });
      });
    }
  }

  showUpdateToast() {
    const toast = document.getElementById('sw-update-toast');
    if (toast) {
      toast.classList.remove('hidden');
      const btn = document.getElementById('btn-sw-reload');
      if (btn) {
        btn.addEventListener('click', () => {
          if (this.swRegistration && this.swRegistration.waiting) {
            this.swRegistration.waiting.postMessage({ action: 'skipWaiting' });
          } else {
            window.location.reload();
          }
        });
      }
    }
  }
}

// Instantiate and start on DOM load
window.addEventListener('DOMContentLoaded', () => {
  window.App = new ApplicationController();
  window.App.init();
});

/**
 * Safety UX: Slide-to-Arm, Fail-Closed Stale Watchdog, Fault Banner & Web Audio/Haptics.
 */

import { CONFIG } from './config.js';
import { State } from './state.js';
import { Api } from './api.js';

class SafetySupervisor {
  constructor() {
    this.audioCtx = null;
    this.wakeLock = null;

    this.slideTrack = null;
    this.slideKnob = null;
    this.isSliding = false;
    this.slideStartX = 0;
    this.slideCurrentX = 0;
    this.slideMaxDistance = 0;

    this.faultBannerEl = null;
    this.staleOverlayEl = null;
    this.estopUndeliveredBannerEl = null;
    this.insecureBannerEl = null;

    this.watchdogTimer = null;
  }

  init() {
    this.slideTrack = document.getElementById('slide-arm-track');
    this.slideKnob = document.getElementById('slide-arm-knob');
    this.faultBannerEl = document.getElementById('fault-banner');
    this.staleOverlayEl = document.getElementById('stale-overlay');
    this.estopUndeliveredBannerEl = document.getElementById('estop-undelivered-banner');
    this.insecureBannerEl = document.getElementById('insecure-context-banner');

    this.initSlideToArm();
    this.initWatchdog();
    this.initAudioContextUnlock();
    this.initVisibilityListeners();
    this.checkSecureContext();
    this.requestWakeLock();

    // Subscribe to state changes
    State.on('robotState', (s) => this.updateUiState(s));
    State.on('batteryVoltage', () => this.validateArmEligibility());
    State.on('connStatus', () => this.validateArmEligibility());
    State.on('isController', () => this.validateArmEligibility());
    State.on('errorFlags', () => this.renderFaultStatus());
    State.on('estopPending', (pending) => this.renderEstopPendingStatus(pending));
  }

  checkSecureContext() {
    const isSecure = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    if (!isSecure && this.insecureBannerEl) {
      this.insecureBannerEl.classList.remove('hidden');
    }
  }

  initAudioContextUnlock() {
    const unlock = () => {
      if (!this.audioCtx) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          this.audioCtx = new AudioCtx();
        }
      } else if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
    };
    window.addEventListener('pointerdown', unlock);
    window.addEventListener('keydown', unlock);
  }

  playTone(frequencyHz, durationMs, type = 'sine') {
    if (!this.audioCtx) return;
    try {
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(frequencyHz, this.audioCtx.currentTime);

      gain.gain.setValueAtTime(0.15, this.audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + (durationMs / 1000));

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start();
      osc.stop(this.audioCtx.currentTime + (durationMs / 1000));
    } catch (_) {}
  }

  vibrate(pattern) {
    if (navigator.vibrate) {
      try { navigator.vibrate(pattern); } catch (_) {}
    }
  }

  initSlideToArm() {
    if (!this.slideTrack || !this.slideKnob) return;

    const onStart = (e) => {
      if (!this.canArm()) return;
      this.isSliding = true;
      this.slideStartX = e.clientX || (e.touches && e.touches[0].clientX);
      const trackRect = this.slideTrack.getBoundingClientRect();
      const knobRect = this.slideKnob.getBoundingClientRect();
      this.slideMaxDistance = trackRect.width - knobRect.width - 8;

      if (this.slideKnob.setPointerCapture && e.pointerId) {
        try { this.slideKnob.setPointerCapture(e.pointerId); } catch (_) {}
      }
      this.slideKnob.classList.add('sliding');
    };

    const onMove = (e) => {
      if (!this.isSliding) return;
      const currentX = e.clientX || (e.touches && e.touches[0].clientX);
      let dx = currentX - this.slideStartX;
      if (dx < 0) dx = 0;
      if (dx > this.slideMaxDistance) dx = this.slideMaxDistance;

      this.slideCurrentX = dx;
      this.slideKnob.style.transform = `translateX(${dx}px)`;

      // Confirm threshold reached (88% of travel)
      if (dx >= this.slideMaxDistance * 0.88) {
        this.confirmArm();
      }
    };

    const onEnd = (e) => {
      if (!this.isSliding) return;
      this.isSliding = false;
      this.slideKnob.classList.remove('sliding');
      this.slideKnob.style.transform = 'translateX(0px)';
      if (this.slideKnob.releasePointerCapture && e && e.pointerId) {
        try { this.slideKnob.releasePointerCapture(e.pointerId); } catch (_) {}
      }
    };

    this.slideKnob.addEventListener('pointerdown', onStart);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onEnd);
    window.addEventListener('pointercancel', onEnd);
  }

  canArm() {
    const isDisarmed = State.get('robotState') === 'DISARMED';
    const isConnected = State.get('connected');
    const isController = State.get('isController');
    const battOk = State.get('batteryVoltage') >= CONFIG.BATTERY.ARM_MIN_VOLTS;

    const now = performance.now();
    const browserAge = now - (State.get('lastRxTimestamp') || 0);
    const packetAge = State.get('packetAgeMs');

    // Fail-closed freshness check
    const isFresh = (browserAge <= CONFIG.STALE_TELEMETRY_THRESHOLD_MS) &&
                    (typeof packetAge === 'number' && packetAge <= CONFIG.STALE_TELEMETRY_THRESHOLD_MS);

    const isEstop = State.get('estopActive') || State.get('estopPending');

    return isDisarmed && isConnected && isController && battOk && isFresh && !isEstop;
  }

  validateArmEligibility() {
    if (!this.slideTrack) return;
    const eligible = this.canArm();
    const label = document.getElementById('slide-arm-label');

    if (eligible) {
      this.slideTrack.classList.remove('disabled');
      if (label) label.textContent = 'SLIDE TO ARM ROBOT ❯❯';
    } else {
      this.slideTrack.classList.add('disabled');
      let reason = 'CANNOT ARM: ';
      if (!State.get('connected')) reason += 'NO LINK';
      else if (!State.get('isController')) reason += 'READ-ONLY OBSERVER';
      else if (State.get('estopActive') || State.get('estopPending')) reason += 'E-STOP ACTIVE';
      else if (State.get('robotState') !== 'DISARMED') reason += `STATE IS ${State.get('robotState')}`;
      else if (State.get('batteryVoltage') < CONFIG.BATTERY.ARM_MIN_VOLTS) reason += `LOW BATT (<${CONFIG.BATTERY.ARM_MIN_VOLTS}V)`;
      else reason += 'STALE TELEMETRY (>300ms)';

      if (label) label.textContent = reason;
    }
  }

  confirmArm() {
    this.isSliding = false;
    this.slideKnob.style.transform = 'translateX(0px)';
    this.playTone(CONFIG.AUDIO.BEEP_ARM_HZ, 180, 'triangle');
    this.vibrate([80, 50, 120]);

    State.addLog('SAFETY', 'Arming confirmed via Slide-to-Arm');
    Api.sendArmState('CALIBRATING');
  }

  initWatchdog() {
    clearInterval(this.watchdogTimer);
    this.watchdogTimer = setInterval(() => {
      const lastRx = State.get('lastRxTimestamp');
      const now = performance.now();
      const browserAge = lastRx ? (now - lastRx) : 9999;
      const packetAge = State.get('packetAgeMs');

      // Fail-closed stale condition: browser age > 300 ms OR Mega packet_age_ms > 300 ms OR null/missing
      const isStale = (browserAge > CONFIG.STALE_TELEMETRY_THRESHOLD_MS) ||
                      (typeof packetAge !== 'number' || isNaN(packetAge) || packetAge > CONFIG.STALE_TELEMETRY_THRESHOLD_MS);

      if (State.get('connected') && isStale) {
        if (State.get('connStatus') !== 'STALE') {
          State.set('connStatus', 'STALE');
          State.addLog('WARN', `Telemetry stale! Browser age: ${Math.round(browserAge)}ms, Mega age: ${packetAge}ms. Controls locked.`);
        }
        if (this.staleOverlayEl) {
          this.staleOverlayEl.classList.remove('hidden');
        }
        this.zeroInputs();
      } else if (State.get('connStatus') === 'STALE' && !isStale) {
        State.set('connStatus', 'ONLINE');
        if (this.staleOverlayEl) {
          this.staleOverlayEl.classList.add('hidden');
        }
      }

      this.validateArmEligibility();
    }, 100);
  }

  renderFaultStatus() {
    const rState = State.get('robotState');
    const flags = State.get('errorFlags');
    const desc = State.get('errorDesc');

    if (rState === 'FAULT' || flags !== 0) {
      if (this.faultBannerEl) {
        this.faultBannerEl.classList.remove('hidden');
        const codeEl = document.getElementById('fault-code-text');
        const hintEl = document.getElementById('fault-recovery-hint');

        if (codeEl) codeEl.textContent = `FAULT [0x${flags.toString(16).padStart(2, '0').toUpperCase()}]: ${desc}`;

        if (hintEl) {
          if (flags & 0x01) {
            hintEl.textContent = 'Recovery: Tilt > 45° (Pitch) or > 35° (Roll). Place robot upright on level ground, click "Clear Fault", then re-arm.';
          } else if (flags & 0x02) {
            hintEl.textContent = 'Recovery: USB serial communication lost (>400ms). Check Pi-to-Mega USB cable.';
          } else if (flags & 0x04) {
            hintEl.textContent = 'Recovery: Critical Battery (<9.6V). Replace or charge 3S LiPo immediately.';
          } else if (flags & 0x10) {
            hintEl.textContent = 'Recovery: E-STOP latched. Ensure safety perimeter is clear, click "Clear Fault" to return to DISARMED.';
          } else {
            hintEl.textContent = 'Recovery: Check motor drivers, clear fault, and recalibrate.';
          }
        }
      }
    } else {
      if (this.faultBannerEl) {
        this.faultBannerEl.classList.add('hidden');
      }
    }
  }

  renderEstopPendingStatus(pending) {
    if (this.estopUndeliveredBannerEl) {
      this.estopUndeliveredBannerEl.classList.toggle('hidden', !pending);
    }
  }

  updateUiState(newState) {
    this.renderFaultStatus();
    this.validateArmEligibility();

    const disarmBtn = document.getElementById('btn-disarm');
    if (disarmBtn) {
      disarmBtn.classList.toggle('hidden', newState !== 'ARMED');
    }
  }

  zeroInputs() {
    State.set('linearX', 0.0);
    State.set('angularZ', 0.0);
  }

  initVisibilityListeners() {
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.zeroInputs();
        State.addLog('SAFETY', 'Page hidden; auto-zeroed drive commands');
      }
    });

    window.addEventListener('blur', () => {
      this.zeroInputs();
      State.addLog('SAFETY', 'Window blur; auto-zeroed drive commands');
    });
  }

  async requestWakeLock() {
    if ('wakeLock' in navigator) {
      try {
        this.wakeLock = await navigator.wakeLock.request('screen');
        this.wakeLock.addEventListener('release', () => {
          this.wakeLock = null;
        });
      } catch (_) {}
    }
  }
}

export const Safety = new SafetySupervisor();

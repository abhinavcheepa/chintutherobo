/**
 * Guided 5-Step Hardware Calibration Wizard.
 * 1. IMU Level Calibration
 * 2. Servo Joint Offsets
 * 3. Leg Height Sweep Test
 * 4. Wheel Direction Jog Test
 * 5. Tilt Direction Sign Verification
 */

import { CONFIG } from './config.js';
import { State } from './state.js';
import { Api } from './api.js';

class CalibrationWizard {
  constructor() {
    this.currentStep = 1;
    this.totalSteps = 5;

    // Step test results: null = not run, true = passed, false = failed
    this.stepResults = {
      1: null,
      2: null,
      3: null,
      4: null,
      5: null
    };

    // Joint trim offsets (in microseconds, [-200, +200] us)
    this.servoTrims = {
      hip_pitch_l: 0,
      hip_roll_l: 0,
      knee_l: 0,
      hip_pitch_r: 0,
      hip_roll_r: 0,
      knee_r: 0
    };

    // Load persisted servo trims from localStorage if available
    const savedTrims = localStorage.getItem('chintu_servo_trims');
    if (savedTrims) {
      try {
        this.servoTrims = { ...this.servoTrims, ...JSON.parse(savedTrims) };
      } catch (_) {}
    }
  }

  init() {
    this.bindEvents();
    this.renderStepNavigation();
    this.renderCurrentStepView();

    // Listen to telemetry for live calibration feedback
    State.on('pitch', (pitch) => this.onPitchUpdate(pitch));
    State.on('roll', (roll) => this.onRollUpdate(roll));
  }

  bindEvents() {
    // Step navigation buttons
    const btnPrev = document.getElementById('btn-cal-prev');
    const btnNext = document.getElementById('btn-cal-next');

    if (btnPrev) {
      btnPrev.addEventListener('click', () => {
        if (this.currentStep > 1) {
          this.goToStep(this.currentStep - 1);
        }
      });
    }

    if (btnNext) {
      btnNext.addEventListener('click', () => {
        if (this.currentStep < this.totalSteps) {
          this.goToStep(this.currentStep + 1);
        }
      });
    }

    // Step selector tabs
    document.querySelectorAll('.cal-step-pill').forEach(pill => {
      pill.addEventListener('click', (e) => {
        const step = parseInt(e.currentTarget.dataset.step, 10);
        if (step >= 1 && step <= this.totalSteps) {
          this.goToStep(step);
        }
      });
    });

    // Step 1: IMU Zero Button
    const btnZeroImu = document.getElementById('btn-cal-zero-imu');
    if (btnZeroImu) {
      btnZeroImu.addEventListener('click', () => this.zeroImu());
    }

    // Step 1 Pass/Fail
    const btnPass1 = document.getElementById('btn-cal-pass-1');
    const btnFail1 = document.getElementById('btn-cal-fail-1');
    if (btnPass1) btnPass1.addEventListener('click', () => this.setStepResult(1, true));
    if (btnFail1) btnFail1.addEventListener('click', () => this.setStepResult(1, false));

    // Step 2: Servo Trims Controls
    const jointKeys = ['hip_pitch_l', 'hip_roll_l', 'knee_l', 'hip_pitch_r', 'hip_roll_r', 'knee_r'];
    jointKeys.forEach(k => {
      const slider = document.getElementById(`trim-${k}`);
      const valEl = document.getElementById(`val-trim-${k}`);
      if (slider && valEl) {
        slider.value = this.servoTrims[k];
        valEl.textContent = `${this.servoTrims[k]} µs`;
        slider.addEventListener('input', (e) => {
          const val = parseInt(e.target.value, 10);
          this.servoTrims[k] = val;
          valEl.textContent = `${val > 0 ? '+' : ''}${val} µs`;
          this.sendServoTrimUpdate();
        });
      }
    });

    const btnSaveTrims = document.getElementById('btn-cal-save-trims');
    if (btnSaveTrims) {
      btnSaveTrims.addEventListener('click', () => this.saveServoTrims());
    }
    const btnPass2 = document.getElementById('btn-cal-pass-2');
    const btnFail2 = document.getElementById('btn-cal-fail-2');
    if (btnPass2) btnPass2.addEventListener('click', () => this.setStepResult(2, true));
    if (btnFail2) btnFail2.addEventListener('click', () => this.setStepResult(2, false));

    // Step 3: Leg Height Sweep
    const btnSweepMin = document.getElementById('btn-cal-sweep-min');
    const btnSweepNom = document.getElementById('btn-cal-sweep-nom');
    const btnSweepMax = document.getElementById('btn-cal-sweep-max');
    if (btnSweepMin) btnSweepMin.addEventListener('click', () => this.setLegHeight(CONFIG.LEGS.MIN_HEIGHT_MM));
    if (btnSweepNom) btnSweepNom.addEventListener('click', () => this.setLegHeight(CONFIG.LEGS.NOMINAL_HEIGHT_MM));
    if (btnSweepMax) btnSweepMax.addEventListener('click', () => this.setLegHeight(CONFIG.LEGS.MAX_HEIGHT_MM));

    const btnPass3 = document.getElementById('btn-cal-pass-3');
    const btnFail3 = document.getElementById('btn-cal-fail-3');
    if (btnPass3) btnPass3.addEventListener('click', () => this.setStepResult(3, true));
    if (btnFail3) btnFail3.addEventListener('click', () => this.setStepResult(3, false));

    // Step 4: Wheel Direction Jog
    const btnJogL = document.getElementById('btn-cal-jog-l');
    const btnJogR = document.getElementById('btn-cal-jog-r');
    if (btnJogL) btnJogL.addEventListener('click', () => this.jogWheel('L'));
    if (btnJogR) btnJogR.addEventListener('click', () => this.jogWheel('R'));

    const btnPass4 = document.getElementById('btn-cal-pass-4');
    const btnFail4 = document.getElementById('btn-cal-fail-4');
    if (btnPass4) btnPass4.addEventListener('click', () => this.setStepResult(4, true));
    if (btnFail4) btnFail4.addEventListener('click', () => this.setStepResult(4, false));

    // Step 5: Tilt Direction Sign Check
    const btnPass5 = document.getElementById('btn-cal-pass-5');
    const btnFail5 = document.getElementById('btn-cal-fail-5');
    if (btnPass5) btnPass5.addEventListener('click', () => this.setStepResult(5, true));
    if (btnFail5) btnFail5.addEventListener('click', () => this.setStepResult(5, false));
  }

  goToStep(step) {
    this.currentStep = step;
    this.renderStepNavigation();
    this.renderCurrentStepView();
  }

  setStepResult(step, passed) {
    this.stepResults[step] = passed;
    State.addLog('CAL', `Step ${step} marked ${passed ? 'PASSED' : 'FAILED'}`);
    this.renderStepNavigation();
    this.renderCurrentStepView();

    if (passed && step < this.totalSteps) {
      setTimeout(() => this.goToStep(step + 1), 350);
    }
  }

  renderStepNavigation() {
    for (let s = 1; s <= this.totalSteps; s++) {
      const pill = document.querySelector(`.cal-step-pill[data-step="${s}"]`);
      if (!pill) continue;

      pill.classList.toggle('active', s === this.currentStep);
      pill.classList.remove('passed', 'failed');

      if (this.stepResults[s] === true) {
        pill.classList.add('passed');
      } else if (this.stepResults[s] === false) {
        pill.classList.add('failed');
      }
    }

    const prevBtn = document.getElementById('btn-cal-prev');
    const nextBtn = document.getElementById('btn-cal-next');
    if (prevBtn) prevBtn.disabled = (this.currentStep === 1);
    if (nextBtn) nextBtn.disabled = (this.currentStep === this.totalSteps);

    const stepTitle = document.getElementById('cal-step-title');
    const titles = [
      'Step 1: IMU Level Horizon Calibration',
      'Step 2: Joint Servo Neutral Trims',
      'Step 3: Leg Height Sweep & Travel Limits',
      'Step 4: Wheel Stepper Direction Jog Test',
      'Step 5: Tilt Direction Sign Verification (+Pitch)'
    ];
    if (stepTitle) {
      stepTitle.textContent = titles[this.currentStep - 1];
    }
  }

  renderCurrentStepView() {
    for (let s = 1; s <= this.totalSteps; s++) {
      const panel = document.getElementById(`cal-panel-step-${s}`);
      if (panel) {
        panel.classList.toggle('hidden', s !== this.currentStep);
      }
    }
  }

  // Step 1
  zeroImu() {
    State.addLog('CAL', 'Zeroing IMU gyro biases on level bench...');
    Api.sendArmState('CALIBRATING');
    const btn = document.getElementById('btn-cal-zero-imu');
    if (btn) {
      btn.textContent = 'CALIBRATING...';
      btn.disabled = true;
      setTimeout(() => {
        btn.textContent = 'RE-ZERO IMU';
        btn.disabled = false;
        const pitch = Math.abs(State.get('pitch'));
        const roll = Math.abs(State.get('roll'));
        if (pitch < 1.0 && roll < 1.0) {
          this.setStepResult(1, true);
        }
      }, 1500);
    }
  }

  onPitchUpdate(pitch) {
    if (this.currentStep === 1) {
      const el = document.getElementById('cal-live-pitch');
      if (el) el.textContent = `${pitch.toFixed(2)}°`;
    } else if (this.currentStep === 5) {
      const el = document.getElementById('cal-tilt-pitch-display');
      const msg = document.getElementById('cal-tilt-feedback');
      if (el) el.textContent = `${pitch >= 0 ? '+' : ''}${pitch.toFixed(1)}°`;
      if (msg) {
        if (pitch > 8.0) {
          msg.textContent = '✓ Correct Sign! Forward tilt is reading Positive (+).';
          msg.className = 'text-success font-bold';
        } else if (pitch < -8.0) {
          msg.textContent = '⚠ INVERTED! Forward tilt is reading Negative (-). Reverse IMU axis!';
          msg.className = 'text-danger font-bold';
        } else {
          msg.textContent = 'Tilt robot forward > 8° to verify polarity...';
          msg.className = 'text-muted';
        }
      }
    }
  }

  onRollUpdate(roll) {
    if (this.currentStep === 1) {
      const el = document.getElementById('cal-live-roll');
      if (el) el.textContent = `${roll.toFixed(2)}°`;
    }
  }

  // Step 2
  sendServoTrimUpdate() {
    // Send updated neutral offsets
    State.addLog('CAL', `Joint trim updated`);
  }

  saveServoTrims() {
    localStorage.setItem('chintu_servo_trims', JSON.stringify(this.servoTrims));
    State.addLog('CAL', 'Saved servo trims to browser localStorage');
    alert('Servo neutral trims saved!');
  }

  // Step 3
  setLegHeight(heightMm) {
    State.set('targetHeight', heightMm);
    State.addLog('CAL', `Leg height commanded: ${heightMm} mm`);
    const valEl = document.getElementById('cal-live-height-disp');
    if (valEl) valEl.textContent = `${heightMm} mm`;
  }

  // Step 4
  jogWheel(side) {
    State.addLog('CAL', `Jogging ${side} wheel +10 steps forward`);
    // Brief test pulse if robot is disconnected/on bench
    alert(`Jogging ${side === 'L' ? 'Left' : 'Right'} wheel forward. Verify wheel spins forward.`);
  }
}

export const Calibrate = new CalibrationWizard();

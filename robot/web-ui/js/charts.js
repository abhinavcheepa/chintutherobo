/**
 * Real-Time Telemetry Canvas Charts with 30 FPS Cap, 30s Window, and CSV Export.
 */

import { CONFIG } from './config.js';
import { State } from './state.js';

class TelemetryChartManager {
  constructor() {
    this.isPaused = false;
    this.history = [];
    this.maxSamples = CONFIG.CHARTS.MAX_SAMPLES; // 30s * 20Hz = 600 samples

    this.lastRenderTime = 0;
    this.renderIntervalMs = 1000 / CONFIG.CHARTS.FPS_CAP; // ~33.3 ms

    this.cvsPitch = null;
    this.cvsWheels = null;
    this.cvsPower = null;

    this.ctxPitch = null;
    this.ctxWheels = null;
    this.ctxPower = null;
  }

  init() {
    this.cvsPitch = document.getElementById('chart-pitch-stream');
    this.cvsWheels = document.getElementById('chart-wheels-stream');
    this.cvsPower = document.getElementById('chart-power-stream');

    if (this.cvsPitch) this.ctxPitch = this.cvsPitch.getContext('2d');
    if (this.cvsWheels) this.ctxWheels = this.cvsWheels.getContext('2d');
    if (this.cvsPower) this.ctxPower = this.cvsPower.getContext('2d');

    // Subscribe to state changes
    State.on('pitch', () => this.recordSample());

    this.startRenderLoop();
  }

  recordSample() {
    if (this.isPaused) return;

    const sample = {
      timestamp: performance.now(),
      pitch: State.get('pitch'),
      pitchRate: State.get('pitchRate'),
      wheelVelL: State.get('wheelVelL'),
      wheelVelR: State.get('wheelVelR'),
      cmdVelX: State.get('linearX'),
      batteryV: State.get('batteryVoltage'),
      jitterUs: State.get('loopJitterUs')
    };

    this.history.push(sample);
    if (this.history.length > this.maxSamples) {
      this.history.shift();
    }
  }

  setPaused(paused) {
    this.isPaused = paused;
    State.addLog('UI', `Telemetry charting ${paused ? 'PAUSED' : 'RESUMED'}`);
  }

  exportCsv() {
    if (this.history.length === 0) {
      alert('No telemetry recorded yet to export.');
      return;
    }

    const headers = ['time_ms', 'pitch_deg', 'pitch_rate_dps', 'wheel_vel_l', 'wheel_vel_r', 'cmd_vel_x', 'battery_v', 'jitter_us'];
    const rows = this.history.map(s => [
      Math.round(s.timestamp),
      s.pitch.toFixed(2),
      s.pitchRate.toFixed(2),
      s.wheelVelL,
      s.wheelVelR,
      s.cmdVelX.toFixed(3),
      s.batteryV.toFixed(2),
      s.jitterUs
    ]);

    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `chintu_telemetry_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    State.addLog('DATA', `Exported ${this.history.length} telemetry records to CSV.`);
  }

  startRenderLoop() {
    const loop = (now) => {
      if (now - this.lastRenderTime >= this.renderIntervalMs) {
        this.renderAll();
        this.lastRenderTime = now;
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  renderAll() {
    // Only render if Telemetry tab is visible
    if (State.get('activeTab') !== 'telemetry') return;

    this.renderStrip(this.ctxPitch, this.cvsPitch, [
      { key: 'pitch', color: '#00e5ff', label: 'Pitch (°)' },
      { key: 'pitchRate', color: '#ffb300', label: 'Pitch Rate (°/s)' }
    ], -35, 35, true);

    this.renderStrip(this.ctxWheels, this.cvsWheels, [
      { key: 'wheelVelL', color: '#00e676', label: 'Left (st/s)' },
      { key: 'wheelVelR', color: '#e91e63', label: 'Right (st/s)' }
    ], -6000, 6000, true);

    this.renderStrip(this.ctxPower, this.cvsPower, [
      { key: 'batteryV', color: '#ffc107', label: 'Battery (V)' }
    ], 9.5, 12.6, false);
  }

  renderStrip(ctx, cvs, series, minVal, maxVal, drawZero) {
    if (!ctx || !cvs) return;
    const w = cvs.width;
    const h = cvs.height;

    ctx.clearRect(0, 0, w, h);

    // Subtle Grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h * 0.25); ctx.lineTo(w, h * 0.25);
    ctx.moveTo(0, h * 0.75); ctx.lineTo(w, h * 0.75);
    ctx.stroke();

    // Zero Reference
    if (drawZero && minVal < 0 && maxVal > 0) {
      const zeroY = h - ((0 - minVal) / (maxVal - minVal)) * h;
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, zeroY); ctx.lineTo(w, zeroY);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    if (this.history.length < 2) return;

    const step = w / (this.maxSamples - 1);
    const startIdx = this.maxSamples - this.history.length;

    for (const s of series) {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();

      for (let i = 0; i < this.history.length; i++) {
        const val = Math.max(minVal, Math.min(maxVal, this.history[i][s.key] || 0));
        const x = (startIdx + i) * step;
        const y = h - ((val - minVal) / (maxVal - minVal)) * h;

        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }
}

export const Charts = new TelemetryChartManager();

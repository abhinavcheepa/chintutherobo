/* ========================================
   CHINTU — Telemetry Graphs & Metrics
   Canvas graph renderer for real-time sensor
   data streams (Pitch, Speed, Joints, Torque, COM)
   ======================================== */

class TelemetryGraph {
    constructor(canvasId, options = {}) {
        this.canvas = $(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.color = options.color || 'rgba(0, 240, 255, 0.8)';
        this.colors = options.colors || [this.color];
        this.labels = options.labels || ['Value'];
        this.minY = options.minY ?? -20;
        this.maxY = options.maxY ?? 20;
        this.gridColor = 'rgba(0, 240, 255, 0.06)';
        this.textColor = 'rgba(148, 163, 184, 0.6)';
        this.isXY = options.isXY || false;
    }

    draw(datasets) {
        const canvas = this.canvas;
        if (!canvas) return;
        const ctx = this.ctx;
        const w = canvas.width;
        const h = canvas.height;
        const padding = { top: 10, right: 10, bottom: 18, left: 36 };
        const plotW = w - padding.left - padding.right;
        const plotH = h - padding.top - padding.bottom;

        ctx.clearRect(0, 0, w, h);

        // Background gradient
        const bg = ctx.createLinearGradient(0, 0, 0, h);
        bg.addColorStop(0, 'rgba(10, 14, 23, 0.5)');
        bg.addColorStop(1, 'rgba(10, 14, 23, 0.8)');
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, w, h);

        // Grid lines & Y-axis labels
        ctx.strokeStyle = this.gridColor;
        ctx.lineWidth = 1;
        const gridLines = 4;
        for (let i = 0; i <= gridLines; i++) {
            const y = padding.top + (plotH / gridLines) * i;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(w - padding.right, y);
            ctx.stroke();

            const val = this.maxY - ((this.maxY - this.minY) / gridLines) * i;
            ctx.fillStyle = this.textColor;
            ctx.font = '8px JetBrains Mono';
            ctx.textAlign = 'right';
            ctx.fillText(val.toFixed(0), padding.left - 4, y + 3);
        }

        if (this.isXY) {
            // XY plot (for Center of Mass trajectory)
            if (datasets.length >= 2) {
                const xData = datasets[0];
                const yData = datasets[1];
                if (xData.length > 1) {
                    ctx.strokeStyle = this.colors[0];
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    for (let i = 0; i < xData.length; i++) {
                        const px = padding.left + ((xData[i] - this.minY) / (this.maxY - this.minY)) * plotW;
                        const py = padding.top + plotH - ((yData[i] - this.minY) / (this.maxY - this.minY)) * plotH;
                        if (i === 0) ctx.moveTo(px, py);
                        else ctx.lineTo(px, py);
                    }
                    ctx.stroke();

                    // Current point indicator
                    const lastI = xData.length - 1;
                    const lastPx = padding.left + ((xData[lastI] - this.minY) / (this.maxY - this.minY)) * plotW;
                    const lastPy = padding.top + plotH - ((yData[lastI] - this.minY) / (this.maxY - this.minY)) * plotH;
                    ctx.fillStyle = this.colors[0];
                    ctx.shadowColor = this.colors[0];
                    ctx.shadowBlur = 8;
                    ctx.beginPath();
                    ctx.arc(lastPx, lastPy, 4, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.shadowBlur = 0;
                }
            }
            return;
        }

        // Time-series plots
        datasets.forEach((data, di) => {
            if (data.length < 2) return;

            const color = this.colors[di] || this.colors[0];

            // Curve line
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            for (let i = 0; i < data.length; i++) {
                const x = padding.left + (i / (data.length - 1)) * plotW;
                const y = padding.top + plotH - ((data[i] - this.minY) / (this.maxY - this.minY)) * plotH;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.stroke();

            // Glow fill underneath first dataset
            if (di === 0 && data.length > 2) {
                const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + plotH);
                const baseColor = color.replace(/[\d.]+\)$/, '0.15)');
                gradient.addColorStop(0, baseColor);
                gradient.addColorStop(1, 'transparent');
                ctx.fillStyle = gradient;
                ctx.beginPath();
                for (let i = 0; i < data.length; i++) {
                    const x = padding.left + (i / (data.length - 1)) * plotW;
                    const y = padding.top + plotH - ((data[i] - this.minY) / (this.maxY - this.minY)) * plotH;
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }
                ctx.lineTo(padding.left + plotW, padding.top + plotH);
                ctx.lineTo(padding.left, padding.top + plotH);
                ctx.closePath();
                ctx.fill();
            }

            // Current value dot
            if (data.length > 0) {
                const lastX = padding.left + plotW;
                const lastY = padding.top + plotH - ((data[data.length - 1] - this.minY) / (this.maxY - this.minY)) * plotH;
                ctx.fillStyle = color;
                ctx.shadowColor = color;
                ctx.shadowBlur = 6;
                ctx.beginPath();
                ctx.arc(lastX, lastY, 3, 0, Math.PI * 2);
                ctx.fill();
                ctx.shadowBlur = 0;
            }
        });

        // Legends
        if (this.labels.length > 1) {
            let legendX = w - padding.right - 10;
            ctx.font = '7px Rajdhani';
            ctx.textAlign = 'right';
            for (let i = this.labels.length - 1; i >= 0; i--) {
                ctx.fillStyle = this.colors[i] || this.colors[0];
                const textWidth = ctx.measureText(this.labels[i]).width;
                ctx.fillText(this.labels[i], legendX, padding.top + 8);
                ctx.beginPath();
                ctx.arc(legendX - textWidth - 6, padding.top + 5, 3, 0, Math.PI * 2);
                ctx.fill();
                legendX -= textWidth + 20;
            }
        }
    }
}

// ──────────── Graph instances ────────────
const graphs = {};

function initGraphs() {
    graphs.pitch = new TelemetryGraph('graphPitch', {
        color: 'rgba(0, 240, 255, 0.8)',
        minY: -20,
        maxY: 20,
        labels: ['Pitch'],
    });

    graphs.wheelSpeed = new TelemetryGraph('graphWheelSpeed', {
        colors: ['rgba(34, 255, 136, 0.8)', 'rgba(59, 130, 246, 0.7)'],
        minY: -150,
        maxY: 150,
        labels: ['Left', 'Right'],
    });

    graphs.jointAngles = new TelemetryGraph('graphJointAngles', {
        colors: [
            'rgba(0, 240, 255, 0.7)',
            'rgba(139, 92, 246, 0.7)',
            'rgba(255, 140, 0, 0.7)',
            'rgba(255, 59, 92, 0.7)'
        ],
        minY: -120,
        maxY: 90,
        labels: ['L-Hip', 'L-Knee', 'R-Hip', 'R-Knee'],
    });

    graphs.torque = new TelemetryGraph('graphTorque', {
        colors: ['rgba(255, 140, 0, 0.8)', 'rgba(139, 92, 246, 0.7)'],
        minY: -25,
        maxY: 25,
        labels: ['Left Whl', 'Right Whl'],
    });

    graphs.com = new TelemetryGraph('graphCOM', {
        colors: ['rgba(34, 255, 136, 0.8)'],
        minY: -1,
        maxY: 1,
        isXY: true,
        labels: ['COM'],
    });
}

// ──────────── UI updates ────────────

function updateStatusPanel() {
    const r = AppState.robot;
    const sysEl = $('statusSystem');
    if (sysEl) sysEl.textContent = r.system;

    const powEl = $('statusPower');
    const barEl = $('batteryBar');
    if (powEl) powEl.textContent = `${Math.round(r.power)}%`;
    if (barEl) {
        barEl.style.width = `${r.power}%`;
        if (r.power < 20) {
            barEl.style.background = 'linear-gradient(90deg, var(--danger-red), var(--warning-orange))';
            if (powEl) powEl.className = 'status-value error';
        } else if (r.power < 40) {
            barEl.style.background = 'linear-gradient(90deg, var(--warning-orange), #ffcc00)';
            if (powEl) powEl.className = 'status-value warn';
        } else {
            barEl.style.background = 'linear-gradient(90deg, var(--neon-green), var(--accent-cyan))';
            if (powEl) powEl.className = 'status-value';
        }
    }

    const tempEl = $('statusTemp');
    if (tempEl) {
        tempEl.textContent = `${r.temp.toFixed(1)}°C`;
        tempEl.className = r.temp > 50 ? 'status-value error' : r.temp > 40 ? 'status-value warn' : 'status-value';
    }

    const upEl = $('statusUptime');
    if (upEl) {
        const elapsed = Math.floor((Date.now() - AppState.startTime) / 1000);
        const hrs = Math.floor(elapsed / 3600);
        const mins = Math.floor((elapsed % 3600) / 60);
        upEl.textContent = `${hrs}h ${mins}m`;
    }
}

function updateJointOverlays() {
    const r = AppState.robot;
    const lHip = $('leftHipAngle');
    const lKnee = $('leftKneeAngle');
    const lRPM = $('leftWheelRPM');
    const rHip = $('rightHipAngle');
    const rKnee = $('rightKneeAngle');
    const rRPM = $('rightWheelRPM');

    if (lHip) lHip.textContent = `${r.leftHip.toFixed(1)}°`;
    if (lKnee) lKnee.textContent = `${r.leftKnee.toFixed(1)}°`;
    if (lRPM) lRPM.textContent = `${Math.round(r.leftWheelRPM)} RPM`;
    if (rHip) rHip.textContent = `${r.rightHip.toFixed(1)}°`;
    if (rKnee) rKnee.textContent = `${r.rightKnee.toFixed(1)}°`;
    if (rRPM) rRPM.textContent = `${Math.round(r.rightWheelRPM)} RPM`;
}

function updateGraphs() {
    const t = AppState.telemetry;
    if (graphs.pitch) graphs.pitch.draw([t.pitch]);
    if (graphs.wheelSpeed) graphs.wheelSpeed.draw([t.leftWheelSpeed, t.rightWheelSpeed]);
    if (graphs.jointAngles) graphs.jointAngles.draw([t.leftHipAngle, t.leftKneeAngle, t.rightHipAngle, t.rightKneeAngle]);
    if (graphs.torque) graphs.torque.draw([t.leftTorque, t.rightTorque]);
    if (graphs.com) graphs.com.draw([t.comX, t.comY]);
}

function updateLatency() {
    if (AppState.connection.status === 'connected') {
        if (AppState.connection.protocol === 'websocket') {
            AppState.connection.latency = Math.round(5 + Math.random() * 10);
        }
        const latEl = $('connLatency');
        if (latEl) latEl.textContent = `${AppState.connection.latency} ms`;
    }
}

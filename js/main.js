/* ========================================
   CHINTU — Main Application Entry Point
   Initializes subsystems, starts animation loop,
   manages high-frequency physics/render steps.
   ======================================== */

let lastTime = performance.now();
let updateInterval = null;

function startUpdateLoop() {
    const rate = AppState.telemetry.graphRate || 50;

    updateInterval = setInterval(() => {
        const now = performance.now();
        const dt = (now - lastTime) / 1000;
        lastTime = now;

        // 1. Run simulation / physics step
        simulationStep(dt);

        // 2. Push telemetry data into time-series buffers
        const t = AppState.telemetry;
        const r = AppState.robot;
        const maxPts = t.maxDataPoints;

        t.pitch.push(r.pitch);
        t.leftWheelSpeed.push(r.leftWheelRPM);
        t.rightWheelSpeed.push(r.rightWheelRPM);
        t.leftHipAngle.push(r.leftHip);
        t.leftKneeAngle.push(r.leftKnee);
        t.rightHipAngle.push(r.rightHip);
        t.rightKneeAngle.push(r.rightKnee);
        t.leftTorque.push(r.leftWheelTorque);
        t.rightTorque.push(r.rightWheelTorque);
        t.comX.push(r.comX);
        t.comY.push(r.comY);

        // Trim buffers to max points
        const arrays = [
            t.pitch, t.leftWheelSpeed, t.rightWheelSpeed,
            t.leftHipAngle, t.leftKneeAngle, t.rightHipAngle, t.rightKneeAngle,
            t.leftTorque, t.rightTorque, t.comX, t.comY
        ];
        arrays.forEach(arr => {
            while (arr.length > maxPts) arr.shift();
        });

        // 3. Update dashboard telemetry views
        updateStatusPanel();
        updateJointOverlays();
        updateGraphs();
        updateLatency();

        // 4. Render robot visualization on 2D canvas
        const canvas = $('robotCanvas');
        if (canvas) {
            const ctx = canvas.getContext('2d');
            const rect = canvas.getBoundingClientRect();
            // Handle HiDPI scaling
            if (canvas.width !== rect.width * 2 || canvas.height !== rect.height * 2) {
                canvas.width = rect.width * 2;
                canvas.height = rect.height * 2;
                ctx.scale(2, 2);
            }
            drawRobot(ctx, rect.width, rect.height);
        }

    }, rate);
}

function restartUpdateLoop() {
    if (updateInterval) clearInterval(updateInterval);
    startUpdateLoop();
}

function init() {
    renderPhases();
    initGraphs();
    setupSliders();
    setupEventListeners();
    startUpdateLoop();

    logToConsole('[SYSTEM] Chintu Robot Control Dashboard v1.0 initialized', 'success');
    logToConsole('[SYSTEM] Use Arrow keys / WASD for movement, Space to stop', 'info');
    logToConsole('[SYSTEM] Multi-protocol ready: WebSocket, REST API, Bluetooth', 'info');
    logToConsole('[TIP] Click BALANCE to enable inverted-pendulum balance controller', 'info');

    // Auto-start simulation after short delay
    setTimeout(() => {
        AppState.sim.playing = true;
        const btnSimPlay = $('btnSimPlay');
        if (btnSimPlay) {
            btnSimPlay.classList.add('active');
            btnSimPlay.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> PAUSE';
        }
        logToConsole('[SIM] Simulation engine running', 'success');
    }, 400);
}

document.addEventListener('DOMContentLoaded', init);

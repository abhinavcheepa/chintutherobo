/* ========================================
   CHINTU — Physics Simulation Engine
   Inverted-pendulum model + PID controller
   ======================================== */

function simulationStep(dt) {
    if (!AppState.sim.playing && !AppState.sim.balanceMode) return;

    const r = AppState.robot;
    const s = AppState.sim;
    const speedFactor = s.speed / 100;

    // ── Inverted pendulum dynamics ──
    const gravity        = 9.81;
    const pendulumLength = 0.5;   // m
    const mass           = 5.0;   // kg

    // External torque from movement direction
    let externalTorque = 0;
    if      (AppState.direction === 'forward')  externalTorque = -2 * speedFactor;
    else if (AppState.direction === 'backward') externalTorque =  2 * speedFactor;
    else if (AppState.direction === 'left')     externalTorque = -0.5 * speedFactor;
    else if (AppState.direction === 'right')    externalTorque =  0.5 * speedFactor;

    // Pitch acceleration
    const pitchRad = r.pitch * Math.PI / 180;
    let pitchAccel = (gravity / pendulumLength) * Math.sin(pitchRad) +
                     externalTorque / (mass * pendulumLength * pendulumLength);

    // ── PID Balance Controller ──
    if (s.balanceMode) {
        const error      = 0 - r.pitch;             // target = 0°
        s.pidIntegral   += error * dt;
        s.pidIntegral    = clamp(s.pidIntegral, -50, 50);
        const derivative = (error - s.pidLastError) / dt;
        const control    = s.pid.kp * error + s.pid.ki * s.pidIntegral + s.pid.kd * derivative;
        s.pidLastError   = error;

        const wheelTorque = clamp(control, -20, 20);
        r.leftWheelTorque  = lerp(r.leftWheelTorque,  wheelTorque, 0.3);
        r.rightWheelTorque = lerp(r.rightWheelTorque, wheelTorque, 0.3);

        pitchAccel -= control * 0.1;
    }

    // Update pitch
    r.pitchRate += pitchAccel * dt;
    r.pitchRate *= 0.98;  // damping
    r.pitch     += r.pitchRate * dt;
    r.pitch      = clamp(r.pitch, -45, 45);

    // Sensor noise helper
    const noise = () => randomInRange(-0.3, 0.3);

    // ── Wheel speeds ──
    let targetL = 0, targetR = 0;
    if      (AppState.direction === 'forward')  { targetL =  120 * speedFactor; targetR =  120 * speedFactor; }
    else if (AppState.direction === 'backward') { targetL = -120 * speedFactor; targetR = -120 * speedFactor; }
    else if (AppState.direction === 'left')     { targetL =  -60 * speedFactor; targetR =   60 * speedFactor; }
    else if (AppState.direction === 'right')    { targetL =   60 * speedFactor; targetR =  -60 * speedFactor; }

    r.leftWheelRPM  = lerp(r.leftWheelRPM,  targetL + noise(), 0.1);
    r.rightWheelRPM = lerp(r.rightWheelRPM, targetR + noise(), 0.1);

    // ── Joint angles (from sliders in sim mode) ──
    if (AppState.ui.mode === 'simulation') {
        r.leftHip   = parseFloat($('sliderLHip').value)  + noise();
        r.rightHip  = parseFloat($('sliderRHip').value)  + noise();
        r.leftKnee  = parseFloat($('sliderLKnee').value) + noise();
        r.rightKnee = parseFloat($('sliderRKnee').value) + noise();
    }

    // Torque (when not in balance mode)
    if (!s.balanceMode) {
        r.leftWheelTorque  = lerp(r.leftWheelTorque,  r.leftWheelRPM  * 0.08 + noise(), 0.2);
        r.rightWheelTorque = lerp(r.rightWheelTorque, r.rightWheelRPM * 0.08 + noise(), 0.2);
    }

    // ── COM trajectory ──
    r.comX += (r.leftWheelRPM + r.rightWheelRPM) * 0.0001 * dt;
    r.comY  = 0.4 + Math.sin(r.pitch * Math.PI / 180) * 0.2;

    // ── Slow-changing state ──
    r.temp  = clamp(r.temp + randomInRange(-0.05, 0.08), 25, 65);
    if (s.playing) r.power = clamp(r.power - randomInRange(0, 0.02), 0, 100);
}

/* ========================================
   CHINTU — Robot 2D Canvas Visualization
   Renders chassis, animated legs, pitch attitude,
   ground plane, and orientation indicator.
   ======================================== */

function drawRobot(ctx, width, height) {
    ctx.clearRect(0, 0, width, height);

    const r = AppState.robot;
    const cx = width / 2;
    const cy = height * 0.55;
    const scale = Math.min(width, height) / 500;

    // Background grid
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.04)';
    ctx.lineWidth = 1;
    const gridSize = 30;
    for (let x = 0; x < width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
    }
    for (let y = 0; y < height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }

    // Ground line
    const groundY = cy + 140 * scale;
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.15)';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(0, groundY);
    ctx.lineTo(width, groundY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Ground glow
    const groundGlow = ctx.createLinearGradient(0, groundY - 10, 0, groundY + 30);
    groundGlow.addColorStop(0, 'rgba(0, 240, 255, 0.05)');
    groundGlow.addColorStop(1, 'transparent');
    ctx.fillStyle = groundGlow;
    ctx.fillRect(0, groundY, width, 30);

    ctx.save();
    ctx.translate(cx, cy);

    // Apply pitch rotation
    const pitchRad = r.pitch * Math.PI / 180;
    ctx.rotate(pitchRad);

    // Torso / Chassis
    const torsoW = 80 * scale;
    const torsoH = 50 * scale;
    const torsoRad = 12 * scale;

    // Torso glow & body
    ctx.shadowColor = 'rgba(0, 240, 255, 0.3)';
    ctx.shadowBlur = 20;
    ctx.fillStyle = 'rgba(17, 24, 39, 0.9)';
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.6)';
    ctx.lineWidth = 2;
    roundRect(ctx, -torsoW / 2, -torsoH / 2, torsoW, torsoH, torsoRad);
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Eyes
    const eyeY = -torsoH / 4;
    const eyeGap = 18 * scale;
    ctx.fillStyle = 'rgba(0, 240, 255, 0.8)';
    ctx.shadowColor = 'rgba(0, 240, 255, 0.5)';
    ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(-eyeGap, eyeY, 5 * scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(eyeGap, eyeY, 5 * scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    // Antenna
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.4)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, -torsoH / 2);
    ctx.lineTo(0, -torsoH / 2 - 20 * scale);
    ctx.stroke();
    ctx.fillStyle = 'rgba(34, 255, 136, 0.8)';
    ctx.shadowColor = 'rgba(34, 255, 136, 0.5)';
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.arc(0, -torsoH / 2 - 22 * scale, 4 * scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    // Draw legs
    const legOffsetX = torsoW / 2 - 5 * scale;
    drawLeg(ctx, -legOffsetX, torsoH / 2, r.leftHip, r.leftKnee, r.leftWheelRPM, scale, 'left');
    drawLeg(ctx, legOffsetX, torsoH / 2, r.rightHip, r.rightKnee, r.rightWheelRPM, scale, 'right');

    ctx.restore();

    // Draw pitch indicator in corner
    drawPitchIndicator(ctx, width - 60, 60, r.pitch);
}

function drawLeg(ctx, x, y, hipAngle, kneeAngle, wheelRPM, scale, side) {
    const upperLen = 50 * scale;
    const lowerLen = 45 * scale;
    const wheelR = 14 * scale;

    const hipRad = hipAngle * Math.PI / 180;
    const kneeRad = kneeAngle * Math.PI / 180;

    // Hip joint
    ctx.fillStyle = 'rgba(59, 130, 246, 0.8)';
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.6)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, 5 * scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Upper leg
    const upperEndX = x + Math.sin(hipRad) * upperLen;
    const upperEndY = y + Math.cos(hipRad) * upperLen;

    ctx.strokeStyle = 'rgba(59, 130, 246, 0.7)';
    ctx.lineWidth = 6 * scale;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(upperEndX, upperEndY);
    ctx.stroke();

    // Knee joint
    ctx.fillStyle = 'rgba(139, 92, 246, 0.8)';
    ctx.strokeStyle = 'rgba(139, 92, 246, 0.6)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(upperEndX, upperEndY, 4 * scale, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Lower leg
    const totalAngle = hipRad + kneeRad;
    const lowerEndX = upperEndX + Math.sin(totalAngle) * lowerLen;
    const lowerEndY = upperEndY + Math.cos(totalAngle) * lowerLen;

    ctx.strokeStyle = 'rgba(139, 92, 246, 0.6)';
    ctx.lineWidth = 5 * scale;
    ctx.beginPath();
    ctx.moveTo(upperEndX, upperEndY);
    ctx.lineTo(lowerEndX, lowerEndY);
    ctx.stroke();

    // Wheel
    const wheelGlow = Math.abs(wheelRPM) > 10;
    if (wheelGlow) {
        ctx.shadowColor = 'rgba(34, 255, 136, 0.4)';
        ctx.shadowBlur = 12;
    }
    ctx.strokeStyle = wheelGlow ? 'rgba(34, 255, 136, 0.8)' : 'rgba(100, 116, 139, 0.6)';
    ctx.lineWidth = 3 * scale;
    ctx.beginPath();
    ctx.arc(lowerEndX, lowerEndY, wheelR, 0, Math.PI * 2);
    ctx.stroke();

    // Wheel spokes (animated rotation based on wheel RPM)
    const spokeAngle = (Date.now() / 1000 * wheelRPM * 0.1) % (Math.PI * 2);
    ctx.strokeStyle = wheelGlow ? 'rgba(34, 255, 136, 0.3)' : 'rgba(100, 116, 139, 0.3)';
    ctx.lineWidth = 1.5;
    for (let i = 0; i < 4; i++) {
        const a = spokeAngle + (Math.PI / 2) * i;
        ctx.beginPath();
        ctx.moveTo(lowerEndX, lowerEndY);
        ctx.lineTo(lowerEndX + Math.cos(a) * wheelR * 0.9, lowerEndY + Math.sin(a) * wheelR * 0.9);
        ctx.stroke();
    }
    ctx.shadowBlur = 0;

    // Wheel center hub
    ctx.fillStyle = wheelGlow ? 'rgba(34, 255, 136, 0.6)' : 'rgba(100, 116, 139, 0.4)';
    ctx.beginPath();
    ctx.arc(lowerEndX, lowerEndY, 3 * scale, 0, Math.PI * 2);
    ctx.fill();
}

function drawPitchIndicator(ctx, x, y, pitch) {
    const radius = 30;

    // Background circle
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.15)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.stroke();

    // Pitch arc
    const startAngle = -Math.PI / 2;
    const endAngle = startAngle + (pitch / 45) * Math.PI / 2;
    ctx.strokeStyle = pitch > 10 || pitch < -10 ? 'rgba(255, 140, 0, 0.8)' : 'rgba(0, 240, 255, 0.6)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(x, y, radius, startAngle, endAngle, pitch < 0);
    ctx.stroke();

    // Pitch text
    ctx.fillStyle = 'rgba(0, 240, 255, 0.8)';
    ctx.font = `bold 10px 'Orbitron'`;
    ctx.textAlign = 'center';
    ctx.fillText(`${pitch.toFixed(1)}°`, x, y + 4);
    ctx.font = `7px 'Orbitron'`;
    ctx.fillStyle = 'rgba(148, 163, 184, 0.6)';
    ctx.fillText('PITCH', x, y + 16);
}

function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
}

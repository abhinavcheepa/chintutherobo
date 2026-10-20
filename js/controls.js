/* ========================================
   CHINTU — User Controls & Event Handlers
   D-pad, keyboard shortcuts, joint sliders,
   PID tuner, console CLI, themes, modals.
   ======================================== */

// ──────────── Phase Tracker ────────────

function renderPhases() {
    const list = $('phaseList');
    if (!list) return;
    list.innerHTML = '';
    AppState.phases.forEach(phase => {
        const item = document.createElement('div');
        item.className = `phase-item ${phase.status}`;
        item.setAttribute('data-phase', phase.id);
        let statusIcon = '';
        if (phase.status === 'completed') statusIcon = '✓';
        else if (phase.status === 'active') statusIcon = '▶';
        else statusIcon = '';

        item.innerHTML = `
            <div class="phase-icon">${phase.status === 'completed' ? '✓' : phase.id}</div>
            <span class="phase-name">${phase.name}</span>
            <span class="phase-status-icon">${statusIcon}</span>
        `;
        item.addEventListener('click', () => {
            logToConsole(`[PHASE] Selected Phase ${phase.id}: ${phase.name}`, 'command');
        });
        list.appendChild(item);
    });
}

// ──────────── Slider Bindings ────────────

function setupSliders() {
    const sliders = [
        { id: 'sliderLHip', display: 'valLHip' },
        { id: 'sliderRHip', display: 'valRHip' },
        { id: 'sliderLKnee', display: 'valLKnee' },
        { id: 'sliderRKnee', display: 'valRKnee' },
    ];

    sliders.forEach(({ id, display }) => {
        const slider = $(id);
        const disp = $(display);
        if (!slider || !disp) return;
        slider.addEventListener('input', () => {
            disp.textContent = `${slider.value}°`;
            sendCommand({ type: 'joint', joint: id.replace('slider', ''), angle: parseFloat(slider.value) });
        });
    });

    const speedSlider = $('speedSlider');
    if (speedSlider) {
        speedSlider.addEventListener('input', () => {
            AppState.sim.speed = parseInt(speedSlider.value);
            $('speedValue').textContent = speedSlider.value;
            sendCommand({ type: 'speed', value: parseInt(speedSlider.value) });
        });
    }
}

// ──────────── Theme Switcher ────────────

function applyTheme(theme) {
    const root = document.documentElement;
    switch (theme) {
        case 'midnight':
            root.style.setProperty('--bg-primary', '#060a18');
            root.style.setProperty('--accent-cyan', '#4facfe');
            root.style.setProperty('--accent-blue', '#667eea');
            root.style.setProperty('--neon-green', '#00f2fe');
            break;
        case 'hacker':
            root.style.setProperty('--bg-primary', '#0a100a');
            root.style.setProperty('--accent-cyan', '#00ff41');
            root.style.setProperty('--accent-blue', '#00cc33');
            root.style.setProperty('--neon-green', '#39ff14');
            root.style.setProperty('--accent-purple', '#00ff41');
            break;
        default:
            root.style.removeProperty('--bg-primary');
            root.style.removeProperty('--accent-cyan');
            root.style.removeProperty('--accent-blue');
            root.style.removeProperty('--neon-green');
            root.style.removeProperty('--accent-purple');
    }
}

// ──────────── Interactive Events ────────────

function setupEventListeners() {
    // Protocol Buttons
    const btnWS = $('btnWebSocket');
    const btnRest = $('btnRestAPI');
    const btnBT = $('btnBluetooth');
    const btnRPi = $('btnRaspberryPi');

    function highlightActiveProtocol(protocol) {
        document.querySelectorAll('.conn-mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.protocol === protocol);
        });
    }

    if (btnWS) {
        btnWS.addEventListener('click', () => {
            AppState.connection.protocol = 'websocket';
            highlightActiveProtocol('websocket');
            logToConsole('[UI] WebSocket protocol selected', 'info');
        });
    }

    if (btnRest) {
        btnRest.addEventListener('click', () => {
            AppState.connection.protocol = 'rest';
            highlightActiveProtocol('rest');
            logToConsole('[UI] REST API protocol selected', 'info');
        });
    }

    if (btnBT) {
        btnBT.addEventListener('click', () => {
            AppState.connection.protocol = 'bluetooth';
            highlightActiveProtocol('bluetooth');
            logToConsole('[UI] Bluetooth protocol selected', 'info');
        });
    }

    if (btnRPi) {
        btnRPi.addEventListener('click', () => {
            AppState.connection.protocol = 'rpi';
            highlightActiveProtocol('rpi');
            const hostInput = $('inputHost');
            if (hostInput && (!hostInput.value || hostInput.value === 'localhost')) {
                hostInput.value = 'raspberrypi.local';
            }
            logToConsole('[UI] Raspberry Pi Bridge mode selected', 'info');
        });
    }

    // IP Presets Chips (Localhost, RPi, Robot AP)
    document.querySelectorAll('.preset-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.preset-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            if ($('inputHost')) $('inputHost').value = chip.dataset.host;
            if ($('inputPort')) $('inputPort').value = chip.dataset.port;
            logToConsole(`[CONFIG] Preset loaded: ${chip.dataset.host}:${chip.dataset.port}`, 'info');
        });
    });

    // Hardware Serial Bridge Buttons
    const btnScanSerial = $('btnScanSerial');
    if (btnScanSerial) {
        btnScanSerial.addEventListener('click', () => {
            logToConsole('[SERIAL] Scanning ports...', 'info');
            fetchSerialPorts();
        });
    }

    const btnConnectSerial = $('btnConnectSerial');
    if (btnConnectSerial) {
        btnConnectSerial.addEventListener('click', () => {
            toggleSerialHardware();
        });
    }

    // Connect / Disconnect Button
    const btnConnect = $('btnConnect');
    if (btnConnect) {
        btnConnect.addEventListener('click', () => {
            if (AppState.connection.status === 'connected') {
                disconnect();
                return;
            }

            switch (AppState.connection.protocol) {
                case 'websocket': connectWebSocket(); break;
                case 'rpi':       connectRaspberryPi(); break;
                case 'rest':      connectREST(); break;
                case 'bluetooth': connectBluetooth(); break;
                default:
                    // Default to Raspberry Pi or WebSocket based on host
                    const host = $('inputHost')?.value || '';
                    if (host.includes('raspberry') || host.includes('192.168.')) {
                        AppState.connection.protocol = 'rpi';
                        highlightActiveProtocol('rpi');
                        connectRaspberryPi();
                    } else {
                        AppState.connection.protocol = 'websocket';
                        highlightActiveProtocol('websocket');
                        connectWebSocket();
                    }
            }
        });
    }

    // D-Pad Direction Buttons
    const dpadBtns = document.querySelectorAll('.dpad-btn');
    dpadBtns.forEach(btn => {
        const handleStart = (e) => {
            e.preventDefault();
            const dir = btn.dataset.dir;
            if (dir === 'stop') {
                AppState.direction = null;
                sendCommand({ type: 'move', direction: 'stop' });
            } else {
                AppState.direction = dir;
                sendCommand({ type: 'move', direction: dir, speed: AppState.sim.speed });
            }
            btn.classList.add('pressed');
        };

        const handleEnd = () => {
            if (btn.dataset.dir !== 'stop') {
                AppState.direction = null;
                sendCommand({ type: 'move', direction: 'stop' });
            }
            btn.classList.remove('pressed');
        };

        btn.addEventListener('mousedown', handleStart);
        btn.addEventListener('mouseup', handleEnd);
        btn.addEventListener('mouseleave', () => btn.classList.remove('pressed'));
        btn.addEventListener('touchstart', handleStart);
        btn.addEventListener('touchend', handleEnd);
    });

    // Keyboard controls (Arrow keys / WASD + Space)
    const keyMap = {
        'ArrowUp': 'forward', 'w': 'forward', 'W': 'forward',
        'ArrowDown': 'backward', 's': 'backward', 'S': 'backward',
        'ArrowLeft': 'left', 'a': 'left', 'A': 'left',
        'ArrowRight': 'right', 'd': 'right', 'D': 'right',
        ' ': 'stop',
    };

    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        const dir = keyMap[e.key];
        if (dir) {
            e.preventDefault();
            if (dir === 'stop') {
                AppState.direction = null;
                sendCommand({ type: 'move', direction: 'stop' });
                const btnStop = $('btnStop');
                if (btnStop) {
                    btnStop.classList.add('pressed');
                    setTimeout(() => btnStop.classList.remove('pressed'), 200);
                }
            } else {
                AppState.direction = dir;
                sendCommand({ type: 'move', direction: dir, speed: AppState.sim.speed });
                document.querySelectorAll('.dpad-btn').forEach(b => b.classList.remove('pressed'));
                const btn = document.querySelector(`.dpad-btn[data-dir="${dir}"]`);
                if (btn) btn.classList.add('pressed');
            }
        }
    });

    document.addEventListener('keyup', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        const dir = keyMap[e.key];
        if (dir && dir !== 'stop') {
            AppState.direction = null;
            sendCommand({ type: 'move', direction: 'stop' });
            document.querySelectorAll('.dpad-btn').forEach(b => b.classList.remove('pressed'));
        }
    });

    // Simulation Play/Pause
    const btnSimPlay = $('btnSimPlay');
    if (btnSimPlay) {
        btnSimPlay.addEventListener('click', () => {
            AppState.sim.playing = !AppState.sim.playing;
            btnSimPlay.classList.toggle('active', AppState.sim.playing);
            btnSimPlay.innerHTML = AppState.sim.playing
                ? '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> PAUSE'
                : '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg> PLAY';
            logToConsole(`[SIM] ${AppState.sim.playing ? 'Playing' : 'Paused'}`, 'info');
            sendCommand({ type: 'sim', action: AppState.sim.playing ? 'play' : 'pause' });
        });
    }

    // Simulation Reset
    const btnSimReset = $('btnSimReset');
    if (btnSimReset) {
        btnSimReset.addEventListener('click', () => {
            AppState.robot.pitch = 0;
            AppState.robot.pitchRate = 0;
            AppState.robot.leftHip = 0;
            AppState.robot.rightHip = 0;
            AppState.robot.leftKnee = 0;
            AppState.robot.rightKnee = 0;
            AppState.robot.leftWheelRPM = 0;
            AppState.robot.rightWheelRPM = 0;
            AppState.robot.leftWheelTorque = 0;
            AppState.robot.rightWheelTorque = 0;
            AppState.robot.comX = 0;
            AppState.robot.comY = 0.4;
            AppState.sim.pidIntegral = 0;
            AppState.sim.pidLastError = 0;
            AppState.direction = null;

            $('sliderLHip').value = 0; $('valLHip').textContent = '0°';
            $('sliderRHip').value = 0; $('valRHip').textContent = '0°';
            $('sliderLKnee').value = 0; $('valLKnee').textContent = '0°';
            $('sliderRKnee').value = 0; $('valRKnee').textContent = '0°';

            Object.keys(AppState.telemetry).forEach(key => {
                if (Array.isArray(AppState.telemetry[key])) AppState.telemetry[key] = [];
            });

            logToConsole('[SIM] Reset complete', 'success');
            sendCommand({ type: 'sim', action: 'reset' });
        });
    }

    // Simulation Step
    const btnSimStep = $('btnSimStep');
    if (btnSimStep) {
        btnSimStep.addEventListener('click', () => {
            simulationStep(0.02);
            logToConsole('[SIM] Single step executed (20ms)', 'info');
            sendCommand({ type: 'sim', action: 'step' });
        });
    }

    // Balance Mode
    const btnBalance = $('btnBalance');
    if (btnBalance) {
        btnBalance.addEventListener('click', () => {
            AppState.sim.balanceMode = !AppState.sim.balanceMode;
            btnBalance.classList.toggle('active', AppState.sim.balanceMode);
            if (AppState.sim.balanceMode) {
                AppState.sim.playing = true;
                if (btnSimPlay) {
                    btnSimPlay.classList.add('active');
                    btnSimPlay.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg> PAUSE';
                }
            }
            logToConsole(`[CTRL] Balance mode ${AppState.sim.balanceMode ? 'ENABLED' : 'DISABLED'}`, AppState.sim.balanceMode ? 'success' : 'warning');
            sendCommand({ type: 'control', mode: AppState.sim.balanceMode ? 'balance' : 'manual' });
        });
    }

    // Robot Stance Presets & E-STOP
    const btnStand = $('btnStanceStand');
    if (btnStand) {
        btnStand.addEventListener('click', () => {
            $('sliderLHip').value = 0; $('valLHip').textContent = '0°';
            $('sliderRHip').value = 0; $('valRHip').textContent = '0°';
            $('sliderLKnee').value = 0; $('valLKnee').textContent = '0°';
            $('sliderRKnee').value = 0; $('valRKnee').textContent = '0°';
            AppState.robot.leftHip = 0; AppState.robot.rightHip = 0;
            AppState.robot.leftKnee = 0; AppState.robot.rightKnee = 0;
            logToConsole('[POSE] 🧍 Applied Stand Pose (0°, 0°)', 'success');
            sendCommand({ type: 'stance', stance: 'stand' });
        });
    }

    const btnCrouch = $('btnStanceCrouch');
    if (btnCrouch) {
        btnCrouch.addEventListener('click', () => {
            $('sliderLHip').value = 30; $('valLHip').textContent = '30°';
            $('sliderRHip').value = 30; $('valRHip').textContent = '30°';
            $('sliderLKnee').value = -60; $('valLKnee').textContent = '-60°';
            $('sliderRKnee').value = -60; $('valRKnee').textContent = '-60°';
            AppState.robot.leftHip = 30; AppState.robot.rightHip = 30;
            AppState.robot.leftKnee = -60; AppState.robot.rightKnee = -60;
            logToConsole('[POSE] 🧎 Applied Crouch Pose (30°, -60°)', 'success');
            sendCommand({ type: 'stance', stance: 'crouch' });
        });
    }

    const btnTiltFwd = $('btnStanceTiltFwd');
    if (btnTiltFwd) {
        btnTiltFwd.addEventListener('click', () => {
            $('sliderLHip').value = -20; $('valLHip').textContent = '-20°';
            $('sliderRHip').value = -20; $('valRHip').textContent = '-20°';
            AppState.robot.leftHip = -20; AppState.robot.rightHip = -20;
            logToConsole('[POSE] 📐 Applied Tilt Forward Pose (-20°)', 'info');
            sendCommand({ type: 'stance', stance: 'tilt_fwd' });
        });
    }

    const btnTiltBack = $('btnStanceTiltBack');
    if (btnTiltBack) {
        btnTiltBack.addEventListener('click', () => {
            $('sliderLHip').value = 20; $('valLHip').textContent = '20°';
            $('sliderRHip').value = 20; $('valRHip').textContent = '20°';
            AppState.robot.leftHip = 20; AppState.robot.rightHip = 20;
            logToConsole('[POSE] 📐 Applied Tilt Backward Pose (20°)', 'info');
            sendCommand({ type: 'stance', stance: 'tilt_back' });
        });
    }

    const btnEStop = $('btnEStop');
    if (btnEStop) {
        btnEStop.addEventListener('click', () => {
            AppState.direction = null;
            AppState.sim.balanceMode = false;
            const btnBal = $('btnBalance');
            if (btnBal) btnBal.classList.remove('active');
            document.querySelectorAll('.dpad-btn').forEach(b => b.classList.remove('pressed'));
            logToConsole('🚨 EMERGENCY STOP: All Motors & Servos Cut!', 'error');
            sendCommand({ type: 'estop' });
            sendCommand({ type: 'move', direction: 'stop' });
        });
    }

    // PID Apply
    const btnPidApply = $('btnPidApply');
    if (btnPidApply) {
        btnPidApply.addEventListener('click', () => {
            AppState.sim.pid.kp = parseFloat($('pidKp').value) || 10;
            AppState.sim.pid.ki = parseFloat($('pidKi').value) || 0.5;
            AppState.sim.pid.kd = parseFloat($('pidKd').value) || 2;
            AppState.sim.pidIntegral = 0;
            logToConsole(`[PID] Updated — Kp: ${AppState.sim.pid.kp}, Ki: ${AppState.sim.pid.ki}, Kd: ${AppState.sim.pid.kd}`, 'success');
            sendCommand({ type: 'pid', kp: AppState.sim.pid.kp, ki: AppState.sim.pid.ki, kd: AppState.sim.pid.kd });
        });
    }

    // Mode Switcher (Sim, Hybrid, Live)
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            AppState.ui.mode = btn.dataset.mode;
            logToConsole(`[MODE] Switched to ${btn.dataset.mode.toUpperCase()} mode`, 'info');
        });
    });

    // Viz Controls (Reset view, Toggle labels)
    const btnResetView = $('btnResetView');
    if (btnResetView) {
        btnResetView.addEventListener('click', () => {
            logToConsole('[VIZ] View reset', 'info');
        });
    }

    const btnToggleLabels = $('btnToggleLabels');
    if (btnToggleLabels) {
        btnToggleLabels.addEventListener('click', () => {
            AppState.ui.showLabels = !AppState.ui.showLabels;
            const lOverlay = $('leftLegOverlay');
            const rOverlay = $('rightLegOverlay');
            if (lOverlay) lOverlay.style.opacity = AppState.ui.showLabels ? '1' : '0';
            if (rOverlay) rOverlay.style.opacity = AppState.ui.showLabels ? '1' : '0';
            logToConsole(`[VIZ] Labels ${AppState.ui.showLabels ? 'shown' : 'hidden'}`, 'info');
        });
    }

    // Console Clear & Send
    const btnConsoleClear = $('btnConsoleClear');
    if (btnConsoleClear) {
        btnConsoleClear.addEventListener('click', () => {
            $('consoleOutput').innerHTML = '';
            logToConsole('[SYSTEM] Console cleared', 'info');
        });
    }

    const consoleInput = $('consoleInput');
    const btnConsoleSend = $('btnConsoleSend');
    if (btnConsoleSend) btnConsoleSend.addEventListener('click', () => sendConsoleCommand());
    if (consoleInput) {
        consoleInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') sendConsoleCommand();
        });
    }

    // Settings Modal
    const btnSettings = $('btnSettings');
    const modalSettings = $('settingsModal');
    const btnCloseSettings = $('btnCloseSettings');

    if (btnSettings && modalSettings) {
        btnSettings.addEventListener('click', () => modalSettings.classList.add('active'));
    }
    if (btnCloseSettings && modalSettings) {
        btnCloseSettings.addEventListener('click', () => modalSettings.classList.remove('active'));
    }
    if (modalSettings) {
        modalSettings.addEventListener('click', (e) => {
            if (e.target === modalSettings) modalSettings.classList.remove('active');
        });
    }

    // Settings inputs
    const setRate = $('settingGraphRate');
    if (setRate) {
        setRate.addEventListener('change', () => {
            const rate = parseInt(setRate.value);
            if (rate >= 16 && rate <= 1000) {
                AppState.telemetry.graphRate = rate;
                if (typeof restartUpdateLoop === 'function') restartUpdateLoop();
                logToConsole(`[SETTINGS] Graph rate: ${rate}ms`, 'info');
            }
        });
    }

    const setPts = $('settingDataPoints');
    if (setPts) {
        setPts.addEventListener('change', () => {
            const pts = parseInt(setPts.value);
            if (pts >= 50 && pts <= 1000) {
                AppState.telemetry.maxDataPoints = pts;
                logToConsole(`[SETTINGS] Data points: ${pts}`, 'info');
            }
        });
    }

    const setTheme = $('settingTheme');
    if (setTheme) {
        setTheme.addEventListener('change', () => {
            AppState.ui.theme = setTheme.value;
            applyTheme(setTheme.value);
            logToConsole(`[THEME] Applied: ${setTheme.value}`, 'info');
        });
    }
}

// ──────────── Terminal Command Parser ────────────

function sendConsoleCommand() {
    const consoleInput = $('consoleInput');
    if (!consoleInput) return;
    const cmd = consoleInput.value.trim();
    if (!cmd) return;
    logToConsole(`> ${cmd}`, 'command');

    if (cmd === 'help') {
        logToConsole('Commands: help, status, ping, reset, balance on/off, speed <0-100>, pid <kp> <ki> <kd>', 'info');
    } else if (cmd === 'status') {
        const r = AppState.robot;
        logToConsole(`Status: ${r.system} | Battery: ${Math.round(r.power)}% | Temp: ${r.temp.toFixed(1)}°C | Pitch: ${r.pitch.toFixed(2)}°`, 'info');
    } else if (cmd === 'ping') {
        logToConsole('PONG! 🏓', 'success');
    } else if (cmd === 'reset') {
        const resetBtn = $('btnSimReset');
        if (resetBtn) resetBtn.click();
    } else if (cmd.startsWith('balance')) {
        const on = cmd.includes('on');
        if (on !== AppState.sim.balanceMode) {
            const balBtn = $('btnBalance');
            if (balBtn) balBtn.click();
        }
    } else if (cmd.startsWith('speed')) {
        const val = parseInt(cmd.split(' ')[1]);
        if (!isNaN(val)) {
            AppState.sim.speed = clamp(val, 0, 100);
            $('speedSlider').value = AppState.sim.speed;
            $('speedValue').textContent = AppState.sim.speed;
            logToConsole(`[SPEED] Set to ${AppState.sim.speed}%`, 'success');
        }
    } else if (cmd.startsWith('pid')) {
        const parts = cmd.split(' ');
        if (parts.length >= 4) {
            $('pidKp').value = parts[1];
            $('pidKi').value = parts[2];
            $('pidKd').value = parts[3];
            const pidBtn = $('btnPidApply');
            if (pidBtn) pidBtn.click();
        }
    } else {
        sendCommand({ type: 'raw', command: cmd });
    }

    consoleInput.value = '';
}

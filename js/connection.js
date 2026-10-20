/* ========================================
   CHINTU — Connection Manager
   WebSocket, REST API, Raspberry Pi & Serial Bridge handlers
   ======================================== */

// ──────────── Data Handling ────────────

function handleIncomingData(data) {
    const r = AppState.robot;
    if (data.pitch !== undefined)            r.pitch = data.pitch;
    if (data.pitchRate !== undefined)         r.pitchRate = data.pitchRate;
    if (data.leftHip !== undefined)           r.leftHip = data.leftHip;
    if (data.rightHip !== undefined)          r.rightHip = data.rightHip;
    if (data.leftKnee !== undefined)          r.leftKnee = data.leftKnee;
    if (data.rightKnee !== undefined)         r.rightKnee = data.rightKnee;
    if (data.leftWheelRPM !== undefined)      r.leftWheelRPM = data.leftWheelRPM;
    if (data.rightWheelRPM !== undefined)     r.rightWheelRPM = data.rightWheelRPM;
    if (data.leftWheelTorque !== undefined)   r.leftWheelTorque = data.leftWheelTorque;
    if (data.rightWheelTorque !== undefined)  r.rightWheelTorque = data.rightWheelTorque;
    if (data.comX !== undefined)              r.comX = data.comX;
    if (data.comY !== undefined)              r.comY = data.comY;
    if (data.power !== undefined)             r.power = data.power;
    if (data.temp !== undefined)              r.temp = data.temp;

    // Live Hardware Link Detection (Raspberry Pi / ESP32 Serial)
    if (data.isHardware !== undefined) {
        r.isHardware = Boolean(data.isHardware);
        AppState.connection.hardwareConnected = r.isHardware;
        AppState.connection.hardwarePort = data.hardwarePort || null;
        updateHardwareUI(r.isHardware, data.hardwarePort);
    }
}

function updateHardwareUI(isHardware, port) {
    const topBadge = $('connHardware');
    const boxBadge = $('serialStatusBadge');
    const statStatus = $('statHwStatus');
    const statPort = $('statHwPort');
    const btnLink = $('btnConnectSerial');

    if (topBadge) {
        if (isHardware) {
            topBadge.textContent = 'HW: ACTIVE';
            topBadge.classList.add('hw-active');
            topBadge.classList.remove('hw-sim');
        } else {
            topBadge.textContent = 'HW: SIM';
            topBadge.classList.remove('hw-active');
            topBadge.classList.add('hw-sim');
        }
    }

    if (boxBadge) {
        boxBadge.textContent = isHardware ? 'HARDWARE LINKED' : 'SIMULATION';
        boxBadge.classList.toggle('active', isHardware);
    }

    if (statStatus) {
        statStatus.textContent = isHardware ? 'Live Hardware' : 'Simulated';
        statStatus.className = isHardware ? 'stat-active' : 'stat-sim';
    }

    if (statPort) {
        statPort.textContent = port || (isHardware ? 'ESP32/UART' : '—');
    }

    if (btnLink) {
        btnLink.textContent = isHardware ? 'Unlink HW' : 'Link HW';
        btnLink.classList.toggle('linked', isHardware);
    }
}

function sendCommand(cmd) {
    const payload = JSON.stringify(cmd);

    if (AppState.connection.status !== 'connected') {
        logToConsole(`[CMD] ${payload} (offline - queued)`, 'warning');
        return;
    }

    switch (AppState.connection.protocol) {
        case 'websocket':
        case 'rpi':
            if (AppState.connection.ws?.readyState === WebSocket.OPEN) {
                AppState.connection.ws.send(payload);
            }
            break;
        case 'rest':
            fetch(`${AppState.connection.restBaseUrl}/command`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: payload,
            }).catch(e => logToConsole(`[REST] Send failed: ${e.message}`, 'error'));
            break;
        case 'bluetooth':
            if (AppState.connection.btCharacteristic) {
                const encoder = new TextEncoder();
                AppState.connection.btCharacteristic.writeValue(encoder.encode(payload))
                    .catch(e => logToConsole(`[BT] Send failed: ${e.message}`, 'error'));
            }
            break;
    }
    logToConsole(`[CMD] ${payload}`, 'command');
}

// ──────────── UI helpers ────────────

function setConnectionState(state) {
    AppState.connection.status = state;
    const dot        = $('connDot');
    const label      = $('connLabel');
    const protocol   = $('connProtocol');
    const latencyEl  = $('connLatency');
    const connectBtn = $('btnConnect');

    dot.classList.remove('connected');
    connectBtn.classList.remove('connecting');

    switch (state) {
        case 'connected':
            dot.classList.add('connected');
            let protoLabel = 'WebSocket';
            if (AppState.connection.protocol === 'rpi') protoLabel = 'Raspberry Pi';
            else if (AppState.connection.protocol === 'rest') protoLabel = 'REST API';
            else if (AppState.connection.protocol === 'bluetooth') protoLabel = 'Bluetooth';

            label.textContent = `Online — ${protoLabel}`;
            protocol.textContent = (AppState.connection.protocol === 'rpi' ? 'RPI' : AppState.connection.protocol)?.toUpperCase() || '—';
            connectBtn.querySelector('.btn-connect-text').textContent = 'DISCONNECT';
            updateSignalBars(4);
            logToConsole(`[CONN] Connected via: ${protoLabel}`, 'success');

            // Trigger port scan from server
            fetchSerialPorts();
            break;
        case 'connecting':
            label.textContent = 'Connecting...';
            connectBtn.classList.add('connecting');
            break;
        case 'disconnected':
            label.textContent   = 'Disconnected';
            protocol.textContent = '—';
            latencyEl.textContent = '— ms';
            connectBtn.querySelector('.btn-connect-text').textContent = 'CONNECT';
            updateSignalBars(0);
            updateHardwareUI(false, null);
            break;
    }

    document.querySelectorAll('.conn-mode-btn').forEach(btn => {
        btn.classList.toggle('active',
            btn.dataset.protocol === AppState.connection.protocol && state === 'connected');
    });
}

function updateSignalBars(level) {
    const bars = $('connSignal').querySelectorAll('rect');
    bars.forEach((bar, i) => {
        bar.style.fill = i < level ? 'var(--neon-green)' : 'var(--text-muted)';
    });
}

// ──────────── WebSocket & Raspberry Pi ────────────

function connectWebSocket(customHost = null, customPort = null) {
    const host = customHost || $('inputHost').value || 'localhost';
    const port = customPort || $('inputPort').value || '8765';
    AppState.connection.host = host;
    AppState.connection.port = port;

    // Dynamically update REST base URL to match selected host
    AppState.connection.restBaseUrl = `http://${host}:8973/api`;

    const url = `ws://${host}:${port}`;
    logToConsole(`[WS] Connecting to ${url}...`, 'info');
    setConnectionState('connecting');

    try {
        const ws = new WebSocket(url);
        AppState.connection.ws = ws;

        ws.onopen = () => {
            if (AppState.connection.protocol !== 'rpi') {
                AppState.connection.protocol = 'websocket';
            }
            setConnectionState('connected');
            logToConsole(`[WS] Connected to ${url}`, 'success');
            ws.send(JSON.stringify({ type: 'handshake', client: 'chintu-dashboard', version: '2.0' }));
        };

        ws.onmessage = (event) => {
            try {
                handleIncomingData(JSON.parse(event.data));
            } catch { logToConsole(`[WS] Raw: ${event.data}`, 'info'); }
        };

        ws.onerror = () => {
            logToConsole(`[WS] Connection error to ${url}`, 'error');
            setConnectionState('disconnected');
        };

        ws.onclose = () => {
            logToConsole('[WS] Connection closed', 'warning');
            setConnectionState('disconnected');
            AppState.connection.ws = null;
        };
    } catch (e) {
        logToConsole(`[WS] Failed: ${e.message}`, 'error');
        setConnectionState('disconnected');
    }
}

// Raspberry Pi direct connection helper
function connectRaspberryPi() {
    AppState.connection.protocol = 'rpi';
    const hostInput = $('inputHost');
    if (!hostInput.value || hostInput.value === 'localhost') {
        hostInput.value = 'raspberrypi.local';
    }
    const host = hostInput.value;
    const port = $('inputPort').value || '8765';
    logToConsole(`[RPI] Connecting to Raspberry Pi at ${host}...`, 'info');
    connectWebSocket(host, port);
}

// ──────────── REST API ────────────

function connectREST() {
    const baseUrl = $('settingRestUrl')?.value || AppState.connection.restBaseUrl;
    AppState.connection.restBaseUrl = baseUrl;
    logToConsole(`[REST] Connecting to ${baseUrl}...`, 'info');
    setConnectionState('connecting');

    fetch(`${baseUrl}/ping`, { method: 'GET', signal: AbortSignal.timeout(5000) })
        .then(res => {
            if (res.ok) {
                AppState.connection.protocol = 'rest';
                setConnectionState('connected');
                logToConsole('[REST] API connected', 'success');
                startRESTPolling();
            } else { throw new Error(`HTTP ${res.status}`); }
        })
        .catch(e => {
            logToConsole(`[REST] ${e.message}. Entering offline mode.`, 'warning');
            AppState.connection.protocol = 'rest';
            setConnectionState('connected');
        });
}

function startRESTPolling() {
    if (AppState.connection.restPollInterval) clearInterval(AppState.connection.restPollInterval);
    AppState.connection.restPollInterval = setInterval(async () => {
        try {
            const start = performance.now();
            const res   = await fetch(`${AppState.connection.restBaseUrl}/telemetry`);
            const data  = await res.json();
            AppState.connection.latency = Math.round(performance.now() - start);
            handleIncomingData(data);
        } catch { /* silent */ }
    }, AppState.telemetry.graphRate * 2);
}

// ──────────── Bluetooth ────────────

async function connectBluetooth() {
    if (!navigator.bluetooth) {
        logToConsole('[BT] Web Bluetooth API not supported in this browser', 'error');
        return;
    }
    logToConsole('[BT] Scanning for Chintu...', 'info');
    setConnectionState('connecting');

    try {
        const device = await navigator.bluetooth.requestDevice({
            filters: [{ namePrefix: 'Chintu' }],
            optionalServices: ['0000ffe0-0000-1000-8000-00805f9b34fb'],
        });

        logToConsole(`[BT] Found: ${device.name}`, 'success');
        AppState.connection.btDevice = device;

        const server         = await device.gatt.connect();
        const service        = await server.getPrimaryService('0000ffe0-0000-1000-8000-00805f9b34fb');
        const characteristic = await service.getCharacteristic('0000ffe1-0000-1000-8000-00805f9b34fb');

        AppState.connection.btCharacteristic = characteristic;
        AppState.connection.protocol = 'bluetooth';
        setConnectionState('connected');
        logToConsole('[BT] Ready', 'success');

        await characteristic.startNotifications();
        characteristic.addEventListener('characteristicvaluechanged', (event) => {
            const val = new TextDecoder().decode(event.target.value);
            try { handleIncomingData(JSON.parse(val)); }
            catch { logToConsole(`[BT] Data: ${val}`, 'info'); }
        });

        device.addEventListener('gattserverdisconnected', () => {
            logToConsole('[BT] Disconnected', 'warning');
            setConnectionState('disconnected');
        });
    } catch (e) {
        logToConsole(`[BT] Failed: ${e.message}`, 'error');
        setConnectionState('disconnected');
    }
}

// ──────────── Serial Hardware Bridge Management ────────────

async function fetchSerialPorts() {
    const select = $('selectSerialPort');
    if (!select) return;

    try {
        const res = await fetch(`${AppState.connection.restBaseUrl}/serial/ports`);
        if (!res.ok) return;
        const data = await res.json();

        select.innerHTML = '<option value="">Auto-Detect Port</option>';
        if (data.ports && data.ports.length > 0) {
            data.ports.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.device;
                opt.textContent = `${p.device} (${p.description.substring(0, 22)})`;
                if (data.connected_port === p.device) opt.selected = true;
                select.appendChild(opt);
            });
            logToConsole(`[SERIAL] Found ${data.ports.length} serial/USB port(s)`, 'info');
        } else {
            const opt = document.createElement('option');
            opt.disabled = true;
            opt.textContent = 'No USB/Serial ports found';
            select.appendChild(opt);
        }

        if (data.connected_port) {
            updateHardwareUI(true, data.connected_port);
        }
    } catch (e) {
        // Silent if server is not running
    }
}

async function toggleSerialHardware() {
    const select = $('selectSerialPort');
    const selectedPort = select ? select.value : '';

    if (AppState.connection.hardwareConnected) {
        // Disconnect
        logToConsole('[SERIAL] Disconnecting hardware serial...', 'info');
        try {
            const res = await fetch(`${AppState.connection.restBaseUrl}/serial/disconnect`, { method: 'POST' });
            if (res.ok) {
                AppState.connection.hardwareConnected = false;
                updateHardwareUI(false, null);
                logToConsole('[SERIAL] Hardware disconnected. Switched to Simulation.', 'warning');
            }
        } catch (e) {
            logToConsole(`[SERIAL] Disconnect failed: ${e.message}`, 'error');
        }
    } else {
        // Connect
        logToConsole(`[SERIAL] Linking hardware on port ${selectedPort || 'auto'}...`, 'info');
        try {
            const res = await fetch(`${AppState.connection.restBaseUrl}/serial/connect`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ port: selectedPort || null, baud: 115200 })
            });
            const data = await res.json();
            if (res.ok) {
                AppState.connection.hardwareConnected = true;
                AppState.connection.hardwarePort = data.port;
                updateHardwareUI(true, data.port);
                logToConsole(`[SERIAL] ✅ Linked to ${data.port} at ${data.baud} baud!`, 'success');
            } else {
                logToConsole(`[SERIAL] ❌ ${data.message || 'Connection failed'}`, 'error');
            }
        } catch (e) {
            logToConsole(`[SERIAL] Server unreachable: ${e.message}`, 'error');
        }
    }
}

// ──────────── Disconnect ────────────

function disconnect() {
    if (AppState.connection.ws) {
        AppState.connection.ws.close();
        AppState.connection.ws = null;
    }
    if (AppState.connection.btDevice?.gatt?.connected) {
        AppState.connection.btDevice.gatt.disconnect();
    }
    if (AppState.connection.restPollInterval) {
        clearInterval(AppState.connection.restPollInterval);
        AppState.connection.restPollInterval = null;
    }
    AppState.connection.protocol = null;
    setConnectionState('disconnected');
    logToConsole('[CONN] Disconnected', 'warning');
}

/* ========================================
   CHINTU — Connection Manager
   WebSocket, REST API, Bluetooth handlers
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
}

function sendCommand(cmd) {
    const payload = JSON.stringify(cmd);

    if (AppState.connection.status !== 'connected') {
        logToConsole(`[CMD] ${payload} (offline - queued)`, 'warning');
        return;
    }

    switch (AppState.connection.protocol) {
        case 'websocket':
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
            label.textContent = `Online — ${
                AppState.connection.protocol === 'websocket' ? 'WebSocket' :
                AppState.connection.protocol === 'rest'      ? 'REST'      : 'Bluetooth'}`;
            protocol.textContent = AppState.connection.protocol?.toUpperCase() || '—';
            connectBtn.querySelector('.btn-connect-text').textContent = 'DISCONNECT';
            updateSignalBars(4);
            logToConsole(`[CONN] Protocol: ${AppState.connection.protocol}`, 'success');
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

// ──────────── WebSocket ────────────

function connectWebSocket() {
    const host = $('inputHost').value || 'localhost';
    const port = $('inputPort').value || '8765';
    AppState.connection.host = host;
    AppState.connection.port = port;

    const url = `ws://${host}:${port}`;
    logToConsole(`[WS] Connecting to ${url}...`, 'info');
    setConnectionState('connecting');

    try {
        const ws = new WebSocket(url);
        AppState.connection.ws = ws;

        ws.onopen = () => {
            AppState.connection.protocol = 'websocket';
            setConnectionState('connected');
            logToConsole(`[WS] Connected to ${url}`, 'success');
            ws.send(JSON.stringify({ type: 'handshake', client: 'chintu-dashboard', version: '1.0' }));
        };

        ws.onmessage = (event) => {
            try {
                handleIncomingData(JSON.parse(event.data));
            } catch { logToConsole(`[WS] Raw: ${event.data}`, 'info'); }
        };

        ws.onerror = () => {
            logToConsole('[WS] Connection error', 'error');
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
        logToConsole('[BT] Web Bluetooth API not supported', 'error');
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

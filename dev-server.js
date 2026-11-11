/**
 * Chintu Biped Robot - Development Simulation & Web-UI Server
 * 
 * Provides:
 * 1. HTTP Server for web-ui (index.html, JS modules, CSS, 3D assets)
 * 2. POST /api/ws-ticket endpoint for authentication handshake
 * 3. WebSocket server (/ws) with 20 Hz telemetry streaming & physics simulation
 * 4. Automatic browser launcher
 * 
 * Usage:
 *   npm run dev
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const { WebSocketServer } = require('ws');

const PORT = parseInt(process.env.PORT || '3456', 10);
const WEB_UI_DIR = path.join(__dirname, 'robot', 'web-ui');

// MIME types mapping
const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.glb': 'model/gltf-binary',
  '.gltf': 'model/gltf+json',
  '.wasm': 'application/wasm'
};

// Simulation State
const sim = {
  state: 'DISARMED',       // DISARMED, CALIBRATING, ARMED, FAULT
  state_code: 0,           // 0: DISARMED, 1: CALIBRATING, 2: ARMED, 3: FAULT
  error_flags: 0x00,
  error_desc: 'NOMINAL',

  battery_voltage: 12.18,
  batt_drop_rate: 0.00005,

  pitch: 0.0,
  pitch_rate: 0.0,
  roll: 0.0,
  yaw_rate: 0.0,

  wheel_pos_l: 0,
  wheel_pos_r: 0,
  wheel_vel_l: 0,
  wheel_vel_r: 0,
  leg_height_l: 135,
  leg_height_r: 135,

  cmd_linear_x: 0.0,
  cmd_angular_z: 0.0,
  cmd_target_height: 135,
  cmd_balance_enable: true,
  last_cmd_id: 0,
  last_cmd_rx_time: Date.now(),
  last_mega_rx_time: Date.now(),

  stale_simulation_until: 0,
  usb_link_lost: false,
  telemetry_jitter_ms: 0,
  cpu_temp: 48.2
};

function updatePhysics(dt) {
  const now = Date.now();
  if (!sim.usb_link_lost) {
    sim.last_mega_rx_time = now;
  }

  // Battery discharge
  const loadFactor = 1.0 + (Math.abs(sim.wheel_vel_l) + Math.abs(sim.wheel_vel_r)) * 0.002;
  sim.battery_voltage = Math.max(9.4, sim.battery_voltage - sim.batt_drop_rate * loadFactor);

  if (sim.battery_voltage < 9.6) {
    sim.error_flags |= 0x04;
    sim.error_desc = 'CRITICAL_LOW_BATT (<9.6V)';
    sim.state = 'FAULT';
    sim.state_code = 3;
  }

  if (sim.state === 'ARMED') {
    // 400ms Comms Timeout Check
    if (now - sim.last_cmd_rx_time > 400) {
      sim.error_flags |= 0x02;
      sim.error_desc = 'COMMS_TIMEOUT (>400ms)';
      sim.state = 'FAULT';
      sim.state_code = 3;
      sim.wheel_vel_l = 0;
      sim.wheel_vel_r = 0;
      return;
    }

    // Balancing dynamics simulation
    const t = (now / 1000) * 4.0;
    const naturalOsc = 1.8 * Math.sin(t) + 0.5 * Math.sin(t * 2.7);
    const driveTilt = sim.cmd_linear_x * 8.0;
    sim.pitch = naturalOsc + driveTilt;
    sim.pitch_rate = 1.8 * 4.0 * Math.cos(t) + 0.5 * 5.4 * Math.cos(t * 2.7);
    sim.roll = 0.4 * Math.sin((now / 1000) * 1.5);

    const targetSteps = Math.round(sim.cmd_linear_x * 800);
    const diffSteps = Math.round(sim.cmd_angular_z * 300);
    sim.wheel_vel_l = targetSteps - diffSteps;
    sim.wheel_vel_r = targetSteps + diffSteps;

    sim.wheel_pos_l += Math.round(sim.wheel_vel_l * dt);
    sim.wheel_pos_r += Math.round(sim.wheel_vel_r * dt);

    sim.leg_height_l += Math.round((sim.cmd_target_height - sim.leg_height_l) * 0.2);
    sim.leg_height_r = sim.leg_height_l;
  } else {
    sim.pitch = 0.0;
    sim.pitch_rate = 0.0;
    sim.roll = 0.0;
    sim.wheel_vel_l = 0;
    sim.wheel_vel_r = 0;
  }
}

// HTTP Server
const server = http.createServer((req, res) => {
  const urlObj = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = decodeURIComponent(urlObj.pathname);

  // REST API Endpoints
  if (req.method === 'POST' && pathname === '/api/ws-ticket') {
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    });
    res.end(JSON.stringify({ ticket: 'mock-sim-ticket', expires_in: 3600 }));
    return;
  }

  if (pathname === '/api/health') {
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    });
    res.end(JSON.stringify({ status: 'ok', mode: 'simulation', node: process.version }));
    return;
  }

  // Simulation controls
  if (pathname === '/api/simulate/clear' && req.method === 'POST') {
    sim.state = 'DISARMED';
    sim.state_code = 0;
    sim.error_flags = 0x00;
    sim.error_desc = 'NOMINAL';
    sim.battery_voltage = 12.20;
    sim.stale_simulation_until = 0;
    sim.usb_link_lost = false;
    sim.telemetry_jitter_ms = 0;
    sim.last_cmd_rx_time = Date.now();
    sim.last_mega_rx_time = Date.now();
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'simulator_cleared' }));
    return;
  }

  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    });
    res.end();
    return;
  }

  // Static File Serving
  let relativePath = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  let filePath = path.join(WEB_UI_DIR, relativePath);

  // Prevent directory traversal
  if (!filePath.startsWith(WEB_UI_DIR)) {
    res.writeHead(403, { 'Content-Type': 'text/plain' });
    res.end('403 Forbidden');
    return;
  }

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      // Fallback for directory or 404
      if (stats && stats.isDirectory()) {
        filePath = path.join(filePath, 'index.html');
      } else {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end(`404 Not Found: ${pathname}`);
        return;
      }
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || 'application/octet-stream';

    res.writeHead(200, {
      'Content-Type': contentType,
      'Cache-Control': 'no-cache, no-store, must-revalidate'
    });

    const stream = fs.createReadStream(filePath);
    stream.pipe(res);
  });
});

// WebSocket Server
const wss = new WebSocketServer({ server, path: '/ws' });

let activeClients = new Set();
let primaryController = null;

wss.on('connection', (ws, req) => {
  activeClients.add(ws);

  let isController = false;
  if (!primaryController) {
    primaryController = ws;
    isController = true;
  }

  // Connection ACK
  ws.send(JSON.stringify({
    type: 'connection_ack',
    is_controller: isController,
    server_time: Date.now() / 1000
  }));

  ws.on('message', (message) => {
    let data;
    try {
      data = JSON.parse(message.toString());
    } catch (e) {
      ws.send(JSON.stringify({ type: 'error', message: 'Malformed JSON' }));
      return;
    }

    switch (data.type) {
      case 'ping':
        ws.send(JSON.stringify({
          type: 'pong',
          client_time: data.client_time || 0
        }));
        break;

      case 'estop':
        sim.state = 'FAULT';
        sim.state_code = 3;
        sim.error_flags = 0x10;
        sim.error_desc = `ESTOP_ACTIVATED_${data.reason || 'UNKNOWN'}`;
        sim.cmd_linear_x = 0.0;
        sim.cmd_angular_z = 0.0;
        ws.send(JSON.stringify({ type: 'estop_ack', status: 'DELIVERED' }));
        break;

      case 'command':
        if (ws !== primaryController) {
          ws.send(JSON.stringify({ type: 'error', message: 'Read-only client: another controller is active' }));
          return;
        }
        sim.last_cmd_rx_time = Date.now();
        sim.cmd_linear_x = parseFloat(data.linear_x || 0.0);
        sim.cmd_angular_z = parseFloat(data.angular_z || 0.0);
        sim.cmd_target_height = parseInt(data.leg_height_l || 135, 10);
        sim.cmd_balance_enable = Boolean(data.balance_enable ?? true);
        sim.last_cmd_id = parseInt(data.command_id || 0, 10);
        break;

      case 'arm_state':
        if (ws !== primaryController) return;
        sim.last_cmd_rx_time = Date.now();
        if (data.state === 'CALIBRATING') {
          sim.state = 'CALIBRATING';
          sim.state_code = 1;
          setTimeout(() => {
            if (sim.state === 'CALIBRATING') {
              sim.state = 'ARMED';
              sim.state_code = 2;
              sim.last_cmd_rx_time = Date.now();
              console.log('[CHINTU SIM] Calibration complete -> Robot is now ARMED.');
            }
          }, 1500);
        } else if (data.state === 'DISARMED' || data.state === 'CLEAR_FAULT') {
          sim.state = 'DISARMED';
          sim.state_code = 0;
          sim.error_flags = 0;
          sim.error_desc = 'NOMINAL';
        } else if (data.state === 'ARMED') {
          sim.state = 'ARMED';
          sim.state_code = 2;
        }
        break;

      case 'pid_set':
      case 'save_eeprom':
        ws.send(JSON.stringify({ type: 'ack', command: data.type }));
        break;
    }
  });

  ws.on('close', () => {
    activeClients.delete(ws);
    if (ws === primaryController) {
      primaryController = activeClients.values().next().value || null;
      if (primaryController) {
        primaryController.send(JSON.stringify({
          type: 'connection_ack',
          is_controller: true
        }));
      }
    }
  });
});

// 20 Hz Telemetry Broadcast Loop
const TICK_DT = 0.05; // 50 ms
setInterval(() => {
  updatePhysics(TICK_DT);

  const now = Date.now();
  if (now < sim.stale_simulation_until || activeClients.size === 0) return;

  const packetAgeMs = Math.max(0, +(now - sim.last_mega_rx_time).toFixed(1));

  const telemetryPacket = JSON.stringify({
    type: 'telemetry',
    timestamp_ms: now,
    state: sim.state,
    state_code: sim.state_code,
    pose: {
      pitch: +sim.pitch.toFixed(2),
      pitch_rate: +sim.pitch_rate.toFixed(2),
      roll: +sim.roll.toFixed(2),
      yaw_rate: +sim.yaw_rate.toFixed(2)
    },
    wheels: {
      pos_left: sim.wheel_pos_l,
      pos_right: sim.wheel_pos_r,
      vel_left: sim.wheel_vel_l,
      vel_right: sim.wheel_vel_r
    },
    legs: {
      height_left: sim.leg_height_l,
      height_right: sim.leg_height_r
    },
    power: {
      battery_voltage: +sim.battery_voltage.toFixed(2),
      v_batt_mv: Math.round(sim.battery_voltage * 1000)
    },
    diagnostics: {
      loop_jitter_us: 42,
      last_cmd_id: sim.last_cmd_id,
      error_flags: sim.error_flags,
      error_desc: sim.error_desc,
      packet_age_ms: packetAgeMs
    },
    system: {
      cpu_temp_c: 48.2
    }
  });

  for (const client of activeClients) {
    if (client.readyState === 1) { // WebSocket.OPEN
      client.send(telemetryPacket);
    }
  }
}, TICK_DT * 1000);

// Start Server
server.listen(PORT, '0.0.0.0', () => {
  const url = `http://localhost:${PORT}`;
  console.log('\n=======================================================');
  console.log('   ⚡ CHINTU ROBOT TELEOPERATION & SIMULATOR ⚡');
  console.log('=======================================================');
  console.log(` > Server running at: ${url}`);
  console.log(` > WebSocket stream:  ws://localhost:${PORT}/ws`);
  console.log(` > Serving files:     ${WEB_UI_DIR}`);
  console.log(' > Press Ctrl+C to stop.');
  console.log('=======================================================\n');

  // Auto-launch browser
  const startCmd = process.platform === 'win32' ? `start ${url}` :
                   process.platform === 'darwin' ? `open ${url}` : `xdg-open ${url}`;
  exec(startCmd, (err) => {
    if (err) {
      console.log(`Open ${url} manually in your browser.`);
    } else {
      console.log(`Opened ${url} in your default browser.`);
    }
  });
});


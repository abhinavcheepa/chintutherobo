/**
 * Central Configuration Constants and Operational Thresholds.
 * Single source of truth for Web-UI operations.
 */

let _inMemoryAuthToken = '';

export const CONFIG = {
  // Network & Communication
  // D3: Token held in JS closure memory only (no localStorage, sessionStorage, or URL query)
  get AUTH_TOKEN() {
    return _inMemoryAuthToken;
  },
  set AUTH_TOKEN(val) {
    _inMemoryAuthToken = val ? String(val).trim() : '';
  },

  WS_PORT: 8000,
  COMMAND_RATE_HZ: 20,           // 50 ms loop during active motion
  KEEPALIVE_RATE_HZ: 10,         // 100 ms loop while ARMED (<= 150 ms requirement)
  STALE_TELEMETRY_THRESHOLD_MS: 300, // Fail-closed threshold for stale lockout
  MAX_RECONNECT_DELAY_MS: 4000,

  // Power & 3S LiPo Voltage Thresholds
  BATTERY: {
    ARM_MIN_VOLTS: 11.40,   // Cannot arm below this rest voltage
    WARN_VOLTS: 10.80,      // Amber warning color under load
    CRITICAL_VOLTS: 9.90,   // Red critical flash / auto-cutoff threshold
    FULL_VOLTS: 12.60,      // 100% reference
    EMPTY_VOLTS: 9.60       // 0% reference
  },

  // Kinematic & Dynamic Limits derived from planar 3-link model:
  // Thigh (L2) = 120 mm, Shank (L3) = 101 mm. Reachable range [85, 175] mm.
  LEGS: {
    MIN_HEIGHT_MM: 85,
    MAX_HEIGHT_MM: 175,
    NOMINAL_HEIGHT_MM: 135, // Nominal balancing stance (knee bent ~100 deg)
    MAX_ROLL_TRIM_DEG: 15.0
  },

  // Driving & Joystick Sensitivity
  DRIVE: {
    DEFAULT_SPEED_LIMIT_MPS: 0.30, // Default speed limit on startup
    GATED_SPEED_LIMIT_MPS: 0.15,   // Cap before Gate 1 & 2 are cleared
    MAX_SPEED_LIMIT_MPS: 0.80,     // Max configurable ceiling
    DEADZONE: 0.08,                // Center deadzone
    EXPO_POWER: 1.8,               // Exponential sensitivity curve
    GENTLE_MODE_MULTIPLIER: 0.50,  // Scale factor in gentle mode
    MAX_YAW_RATE_RAD_S: 2.50
  },

  // Telemetry Canvas Charting
  CHARTS: {
    FPS_CAP: 30,
    HISTORY_SECONDS: 30,
    SAMPLE_RATE_HZ: 20,
    MAX_SAMPLES: 600 // 30s * 20Hz
  },

  // Sound Synthesizer Frequencies (Web Audio API)
  AUDIO: {
    BEEP_ESTOP_HZ: 880,
    BEEP_ARM_HZ: 587,
    BEEP_DISARM_HZ: 330,
    BEEP_WARN_HZ: 440
  }
};

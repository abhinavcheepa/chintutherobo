"""Configuration constants for the robot backend supervisor.
Single source of truth for communication rates, timeouts, kinematic and safety limits.
"""

import hashlib
import os
import sys
from pathlib import Path

# Base directories
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
WEB_UI_DIR = PROJECT_ROOT / "web-ui"
LOG_DIR = PROJECT_ROOT / "logs"
CERTS_DIR = BACKEND_DIR / "certs"

# Ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
CERTS_DIR.mkdir(parents=True, exist_ok=True)

# Serial Port Configuration
SERIAL_PORT = os.getenv("ROBOT_SERIAL_PORT", "/dev/ttyACM0")
SERIAL_BAUD = int(os.getenv("ROBOT_SERIAL_BAUD", "250000"))
SERIAL_RECONNECT_DELAY_S = 2.0

# -----------------------------------------------------------------------------
# TIMING & WATCHDOG CONSTANTS (Single source of truth)
# -----------------------------------------------------------------------------
# 1. Mega firmware comms watchdog: 400 ms (defined in firmware config.h)
FIRMWARE_WATCHDOG_TIMEOUT_S = 0.400

# 2. Pi -> Mega heartbeat interval: 100 ms (10 Hz, independent of browser)
SERIAL_HEARTBEAT_INTERVAL_S = 0.100

# 3. Browser -> Pi command timeout: 300 ms
# If no valid browser command arrives for 300 ms while ARMED, Pi commands zero-velocity
# to the Mega while maintaining heartbeats to prevent Mega comms fault.
BROWSER_COMMAND_TIMEOUT_S = 0.300

# 4. Browser disconnect disarm timeout: 1.0 s
# If controller websocket disconnects while ARMED, zero velocity immediately,
# then request DISARMED if reconnect does not happen within 1.0 s.
DISARM_ON_DISCONNECT_TIMEOUT_S = 1.000

# 5. UI telemetry freshness threshold: 300 ms (fail-closed)
STALE_TELEMETRY_THRESHOLD_S = 0.300

# 6. Rates
TELEMETRY_BROADCAST_INTERVAL_S = 0.050  # 20 Hz output to Web UI
MAX_CLIENT_COMMAND_HZ = 30.0            # Max incoming UI commands/sec per client
MAX_PAYLOAD_BYTES = 4096                # Max allowed WS message size

# -----------------------------------------------------------------------------
# KINEMATIC & SPEED LIMITS
# -----------------------------------------------------------------------------
# Leg link lengths (planar model): Thigh = 120 mm, Shank = 101 mm
LINK_THIGH_MM = 120.0
LINK_SHANK_MM = 101.0
LEG_HEIGHT_MIN_MM = 85.0       # Folded stance (safe margin above 24 mm mechanical bottom)
LEG_HEIGHT_MAX_MM = 175.0      # Extended stance (safe margin below 215 mm singularity)
LEG_HEIGHT_NOMINAL_MM = 135.0  # Nominal driving stance (knee bent ~100 deg)
MAX_ROLL_TRIM_RAD = 0.26       # ~15.0 deg

# Speed & steering limits
SPEED_LIMIT_FREE_RUN_MPS = 0.80   # Free run maximum linear speed
SPEED_LIMIT_GATED_MPS = 0.15      # Bench gate locked ceiling
MAX_YAW_RATE_RAD_S = 2.50         # Max angular rate

# -----------------------------------------------------------------------------
# NETWORK & AUTHENTICATION
# -----------------------------------------------------------------------------
SERVER_HOST = os.getenv("ROBOT_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("ROBOT_PORT", "8000"))
ENVIRONMENT = os.getenv("ROBOT_ENVIRONMENT", "production").lower()
AUTH_TOKEN = os.getenv("ROBOT_AUTH_TOKEN", "")

PROHIBITED_WEAK_WORDS = {
    "admin",
    "secret",
    "password",
    "changeme",
    "12345678",
}

# SHA256 digest of historical default token
LEAKED_DEFAULT_TOKEN_SHA256 = "296e9ca2e54674df885ce2ab5081832b99348b7bb6185a746ad889157420364d"

if not AUTH_TOKEN or not AUTH_TOKEN.strip():
    sys.exit("FATAL: ROBOT_AUTH_TOKEN environment variable is unset or empty. Supervisor refuses to start.")

token_hash = hashlib.sha256(AUTH_TOKEN.strip().encode("utf-8")).hexdigest()
if AUTH_TOKEN.strip().lower() in PROHIBITED_WEAK_WORDS or token_hash == LEAKED_DEFAULT_TOKEN_SHA256:
    sys.exit(f"FATAL: Insecure or default credentials detected in ROBOT_AUTH_TOKEN. Supervisor refuses to start.")

if ENVIRONMENT == "production" and len(AUTH_TOKEN.strip()) < 32:
    sys.exit(f"FATAL: In production mode, ROBOT_AUTH_TOKEN must be at least 32 characters (got {len(AUTH_TOKEN.strip())}). Supervisor refuses to start.")

# CORS & Trusted Hosts configuration
default_cors = "https://192.168.4.1:8000,http://192.168.4.1:8000,https://chintu.robot:8000,http://chintu.robot:8000,https://localhost:8000,http://localhost:8000,http://127.0.0.1:8000"
raw_cors = os.getenv("ROBOT_CORS_ORIGINS", default_cors)
if raw_cors.strip().startswith("["):
    import json
    try:
        CORS_ORIGINS = json.loads(raw_cors)
    except Exception:
        CORS_ORIGINS = [orig.strip().strip("'\"") for orig in raw_cors.strip("[]").split(",") if orig.strip()]
else:
    CORS_ORIGINS = [orig.strip() for orig in raw_cors.split(",") if orig.strip()]

if ENVIRONMENT == "production" and ("*" in CORS_ORIGINS or any(orig == "*" for orig in CORS_ORIGINS)):
    sys.exit("FATAL: Wildcard '*' in ROBOT_CORS_ORIGINS is prohibited in production mode.")

default_hosts = "192.168.4.1,chintu.robot,localhost,127.0.0.1,testserver"
raw_hosts = os.getenv("ROBOT_ALLOWED_HOSTS", default_hosts)
ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]


# TLS / HTTPS configuration
SSL_CERT_FILE = CERTS_DIR / "cert.pem"
SSL_KEY_FILE = CERTS_DIR / "key.pem"
ENABLE_HTTPS = os.getenv("ROBOT_ENABLE_HTTPS", "auto").lower()

# Logging Configuration
ENABLE_FILE_LOGGING = True
LOG_FORMAT = "jsonl"
MAX_LOG_FILE_SIZE_BYTES = 50 * 1024 * 1024

#!/usr/bin/env bash
# Provision /etc/chintu.env with secure permissions (root:chintu, 0600)
set -euo pipefail

ENV_FILE="/etc/chintu.env"

if [[ $EUID -ne 0 ]]; then
   echo "[!] This script must be run as root (sudo)" 1>&2
   exit 1
fi

TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

echo "[+] Generating initial /etc/chintu.env..."
cat <<EOF > "$ENV_FILE"
# /etc/chintu.env - System configuration for Chintu Supervisor
# Ownership: root:chintu | Permissions: 0600
ROBOT_ENVIRONMENT=production
ROBOT_AUTH_TOKEN=${TOKEN}
ROBOT_SERIAL_PORT=/dev/ttyACM0
ROBOT_SERIAL_BAUD=250000
ROBOT_HOST=0.0.0.0
ROBOT_PORT=8000
ROBOT_CORS_ORIGINS=["https://192.168.4.1:8000","http://192.168.4.1:8000","https://chintu.robot:8000","http://chintu.robot:8000"]
ROBOT_ALLOWED_HOSTS=192.168.4.1,chintu.robot,localhost,127.0.0.1
EOF

# Ensure user and group exist
if id -u chintu >/dev/null 2>&1; then
    chown root:chintu "$ENV_FILE"
else
    chown root:root "$ENV_FILE"
fi

chmod 0600 "$ENV_FILE"
echo "[+] Created $ENV_FILE with mode 0600."

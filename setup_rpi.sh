#!/usr/bin/env bash
# ========================================================
# CHINTU — Raspberry Pi Automated Setup Script
# Run this once on your Raspberry Pi:
#   chmod +x setup_rpi.sh
#   sudo ./setup_rpi.sh
# ========================================================

set -e

echo "🤖 ========================================================"
echo "   Setting up CHINTU Robot Controller on Raspberry Pi"
echo "========================================================"

# 1. Update system package lists
echo "📦 Updating apt packages..."
sudo apt update -y

# 2. Install required system dependencies
echo "📦 Installing Python3, Pip, I2C, and Serial tools..."
sudo apt install -y python3 python3-pip python3-dev python3-smbus i2c-tools git

# 3. Add current user to dialout and i2c groups for hardware access without sudo
CURRENT_USER=$(logname || echo $USER)
echo "🔑 Adding user '$CURRENT_USER' to dialout (USB Serial) & i2c groups..."
sudo usermod -a -G dialout,i2c $CURRENT_USER

# 4. Enable I2C and Hardware Serial in raspi-config
echo "⚙️ Enabling I2C and Serial interfaces..."
if command -v raspi-config > /dev/null; then
    sudo raspi-config nonint do_i2c 0 || true
    sudo raspi-config nonint do_serial_cons 1 || true # disable serial console
    sudo raspi-config nonint do_serial_hw 0 || true   # enable serial hardware UART
fi

# 5. Install Python dependencies
echo "🐍 Installing Python packages from requirements.txt..."
pip3 install -r requirements.txt --break-system-packages || pip3 install -r requirements.txt

# 6. Optional: Install systemd service
SERVICE_PATH="/etc/systemd/system/chintu.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Installing systemd service ($SERVICE_PATH)..."
sudo bash -c "cat > $SERVICE_PATH" <<EOF
[Unit]
Description=Chintu Robot Control Platform & Raspberry Pi Bridge
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/server.py --auto-serial
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
echo "👉 To enable auto-start on boot: sudo systemctl enable chintu"
echo "👉 To start now:                 sudo systemctl start chintu"
echo "👉 To check status:              sudo systemctl status chintu"

echo ""
echo "✅ CHINTU Raspberry Pi setup completed successfully!"
echo "   Please reboot once to apply group and I2C changes: sudo reboot"
echo "========================================================"

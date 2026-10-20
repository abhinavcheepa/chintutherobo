#!/usr/bin/env bash
# ========================================================
# CHINTU — Raspberry Pi One-Click Launch Script
# Run: ./start_rpi.sh
# ========================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Get local IP address on WiFi / Ethernet
IP_ADDR=$(hostname -I | awk '{print $1}')
if [ -z "$IP_ADDR" ]; then
    IP_ADDR="localhost"
fi

echo "🤖 ========================================================"
echo "   CHINTU Robot Platform — Starting on Raspberry Pi"
echo "========================================================"
echo "  🌐 Local IP:       $IP_ADDR"
echo "  👉 Web Dashboard:  http://$IP_ADDR:8973"
echo "  👉 Or via mDNS:    http://raspberrypi.local:8973"
echo "  👉 WebSocket:      ws://$IP_ADDR:8765"
echo "========================================================"
echo ""

# Start python server with automatic serial port detection
python3 server.py --auto-serial

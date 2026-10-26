#!/usr/bin/env bash
# Hardened Wi-Fi Access Point Provisioning for Raspberry Pi Supervisor
# Generates per-device dynamic SSID and random 16-character WPA2-PSK
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
   echo "[!] This script must be run as root (sudo)" 1>&2
   exit 1
fi

echo "[+] Installing network prerequisites (hostapd, dnsmasq, nftables)..."
apt-get update
apt-get install -y hostapd dnsmasq rfkill nftables

rfkill unblock wlan || true

echo "[+] Deriving dynamic SSID from MAC address..."
if [[ -f /sys/class/net/wlan0/address ]]; then
    MAC_CLEAN=$(cat /sys/class/net/wlan0/address | tr -d ':' | tr '[:lower:]' '[:upper:]')
    MAC_SUFFIX="${MAC_CLEAN: -4}"
else
    MAC_SUFFIX="BASE"
fi
HOTSPOT_SSID="ChintuRobot_${MAC_SUFFIX}"

echo "[+] Generating dynamic 16-character WPA2-PSK..."
HOTSPOT_PSK=$(tr -dc 'A-Za-z0-9!#%^&*' < /dev/urandom | head -c 16 2>/dev/null || echo "CHANGE_ME_PASSPHRASE_SECURE")

echo "[+] Stopping services for reconfiguration..."
systemctl stop hostapd || true
systemctl stop dnsmasq || true

echo "[+] Configuring static IP on wlan0 (192.168.4.1/24)..."
cat << 'EOF' >> /etc/dhcpcd.conf
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF

echo "[+] Configuring dnsmasq DHCP server..."
mv /etc/dnsmasq.conf /etc/dnsmasq.conf.bak || true
cat << EOF > /etc/dnsmasq.conf
interface=wlan0
dhcp-range=192.168.4.10,192.168.4.50,255.255.255.0,24h
domain=robot
address=/chintu.robot/192.168.4.1
EOF

echo "[+] Configuring hostapd Wi-Fi Access Point (Client Isolation Enabled)..."
cat << EOF > /etc/hostapd/hostapd.conf
interface=wlan0
driver=nl80211
ssid=${HOTSPOT_SSID}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${HOTSPOT_PSK}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
ap_isolate=1
EOF

chmod 0600 /etc/hostapd/hostapd.conf
sed -i 's|#DAEMON_CONF=""|DAEMON_CONF="/etc/hostapd/hostapd.conf"|g' /etc/default/hostapd

echo "[+] Enabling and unmasking services..."
systemctl unmask hostapd
systemctl enable hostapd
systemctl enable dnsmasq

systemctl restart dhcpcd
systemctl restart dnsmasq
systemctl restart hostapd

echo "[+] Configuring nftables firewall..."
cat << 'EOF' > /etc/nftables.conf
#!/usr/sbin/nft -f
flush ruleset

table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;

        # Accept loopback
        iif "lo" accept

        # Accept established/related
        ct state established,related accept

        # DHCP on wlan0
        iif "wlan0" udp dport { 67, 68 } accept

        # Web supervisor on TCP 8000
        tcp dport 8000 accept

        # SSH only on wired interface (eth0)
        iif "eth0" tcp dport 22 accept
    }
    chain forward {
        type filter hook forward priority 0; policy drop;
    }
    chain output {
        type filter hook output priority 0; policy accept;
    }
}
EOF

echo "[+] Testing nftables rules with 120-second automatic rollback safeguard..."
nft -f /etc/nftables.conf
(
  sleep 120
  echo "[*] Safeguard: Reverting firewall to open policy if not confirmed."
  nft flush ruleset
) &
SAFEGUARD_PID=$!

echo "======================================================================"
echo "[+] SUCCESS: Hotspot configured!"
echo "    SSID:       ${HOTSPOT_SSID}"
echo "    Passphrase: ${HOTSPOT_PSK}"
echo "    IP:         192.168.4.1 (or https://chintu.robot:8000)"
echo "    NOTICE:     Firewall safeguard running (PID ${SAFEGUARD_PID})."
echo "                Run 'kill ${SAFEGUARD_PID}' to keep firewall active."
echo "======================================================================"

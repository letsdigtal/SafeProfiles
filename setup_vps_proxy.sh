#!/usr/bin/env bash
# ============================================================================
# SafeProfiles - YOUR OWN static-IP SOCKS5 proxy, on a free/cheap VPS
#
# Where to run: any Ubuntu 20.04+ server you control.
#   Best free option : Oracle Cloud "Always Free" tier (free forever, needs a
#                      card for verification only - $0 charged)
#   Paid later       : any $3-5/month VPS (Hetzner, Racknerd, DigitalOcean...)
#
# What it does:
#   1. installs microsocks (tiny open-source SOCKS5 server)
#   2. runs it as a systemd service (survives reboot)
#   3. opens the firewall
#   4. prints the proxy line to PASTE into SafeProfiles
#
# Usage (as root on the VPS):
#   sudo bash setup_vps_proxy.sh              # random port-less defaults
#   sudo bash setup_vps_proxy.sh 1080 myuser mypass
# ============================================================================
set -euo pipefail

if [ "$(id -u)" != "0" ]; then
  echo "Please run as root:  sudo bash setup_vps_proxy.sh"; exit 1
fi

PORT="${1:-1080}"
PUSER="${2:-sp$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' \n')}"
PPASS="${3:-$(head -c12 /dev/urandom | od -An -tx1 | tr -d ' \n')}"

echo "==> Installing microsocks..."
apt-get update -qq
if ! apt-get install -y -qq microsocks 2>/dev/null; then
  echo "    apt package not available - building from source..."
  apt-get install -y -qq gcc make git
  rm -rf /tmp/ms && git clone --depth 1 https://github.com/rofl0r/microsocks /tmp/ms
  make -C /tmp/ms && cp /tmp/ms/microsocks /usr/local/bin/microsocks
fi
command -v microsocks >/dev/null || { echo "microsocks install failed"; exit 1; }

echo "==> Writing credentials to /etc/safeprofiles-proxy.env (root-only)..."
cat > /etc/safeprofiles-proxy.env <<EOF
PORT=${PORT}
PUSER=${PUSER}
PPASS=${PPASS}
EOF
chmod 600 /etc/safeprofiles-proxy.env

echo "==> Creating systemd service (auto-start on boot)..."
cat > /etc/systemd/system/safeprofiles-proxy.service <<EOF
[Unit]
Description=SafeProfiles SOCKS5 proxy (microsocks)
After=network.target

[Service]
EnvironmentFile=/etc/safeprofiles-proxy.env
ExecStart=/usr/bin/env microsocks -i 0.0.0.0 -p \${PORT} \${PUSER} \${PPASS}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now safeprofiles-proxy.service
sleep 1
systemctl is-active safeprofiles-proxy.service >/dev/null || { journalctl -u safeprofiles-proxy -n 20; exit 1; }

echo "==> Opening firewall (ufw / iptables)..."
if command -v ufw >/dev/null && ufw status | grep -q "active"; then
  ufw allow "${PORT}/tcp" >/dev/null
fi
# Oracle Cloud images ship REJECT rules; insert our ACCEPT before them
iptables -C INPUT -p tcp --dport "${PORT}" -j ACCEPT 2>/dev/null || \
  iptables -I INPUT -p tcp --dport "${PORT}" -j ACCEPT
# make it survive reboot where netfilter-persistent exists
if command -v netfilter-persistent >/dev/null; then netfilter-persistent save; fi

PUBIP=$(curl -s -m 10 https://api.ipify.org || echo YOUR.SERVER.IP)

echo ""
echo "============================================================"
echo "  DONE - your own static SOCKS5 proxy is running"
echo "============================================================"
echo "  Paste this into SafeProfiles (Proxies tab or profile):"
echo ""
echo "      socks5://${PUSER}:${PPASS}@${PUBIP}:${PORT}"
echo ""
echo "  Server IP : ${PUBIP} (static - never rotates)"
echo "  Status    : systemctl status safeprofiles-proxy"
echo "  Logs      : journalctl -u safeprofiles-proxy -f"
echo ""
echo "  ORACLE CLOUD ONLY - if the proxy is unreachable, also add an"
echo "  Ingress Rule in the Oracle console:"
echo "    Networking -> Virtual Cloud Network -> your VCN -> Security Lists"
echo "    -> Add Ingress Rule -> Source 0.0.0.0/0, TCP, Dest port ${PORT}"
echo "============================================================"

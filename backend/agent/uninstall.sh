#!/usr/bin/env bash
# Remove completamente o agente do SMI do servidor.
# Uso:   sudo bash uninstall.sh
# (os pacotes python3/python3-psutil ficam, pois outros programas podem usá-los)
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Rode com sudo: sudo bash uninstall.sh" >&2
  exit 1
fi

systemctl disable --now smi-agent 2>/dev/null || true
rm -f /etc/systemd/system/smi-agent.service
systemctl daemon-reload
rm -rf /opt/smi-agent /etc/smi-agent /var/lib/smi-agent /var/lib/private/smi-agent
echo "Agente do SMI removido."

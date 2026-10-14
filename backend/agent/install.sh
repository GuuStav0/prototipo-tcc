#!/usr/bin/env bash
# Instala o agente do SMI num servidor Ubuntu/Debian.
# Uso (na pasta onde estão estes arquivos):   sudo bash install.sh
#
# O que este script faz (e só isso):
#   - instala os pacotes python3 e python3-psutil (do repositório oficial do Ubuntu);
#   - copia o agente para /opt/smi-agent e o serviço para /etc/systemd/system;
#   - cria /etc/smi-agent/agent.env (permissão 600) se ainda não existir.
# Ele NÃO inicia o serviço: isso é feito depois de editar o agent.env.
# Não altera nginx/apache, PHP, banco de dados, firewall nem os sites.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Rode com sudo: sudo bash install.sh" >&2
  exit 1
fi
cd "$(dirname "$0")"

echo "==> Instalando python3 e python3-psutil (apt)"
apt-get install -y --no-install-recommends python3 python3-psutil

echo "==> Copiando o agente"
install -d -m 755 /opt/smi-agent
install -m 644 smi_agent.py /opt/smi-agent/smi_agent.py

install -d -m 755 /etc/smi-agent
if [ ! -f /etc/smi-agent/agent.env ]; then
  install -m 600 agent.env.example /etc/smi-agent/agent.env
  echo "==> Criado /etc/smi-agent/agent.env (edite antes de iniciar)"
else
  echo "==> /etc/smi-agent/agent.env já existe; mantido"
fi

echo "==> Instalando o serviço systemd"
install -m 644 smi-agent.service /etc/systemd/system/smi-agent.service
systemctl daemon-reload

echo
echo "Teste de leitura (não envia nada):"
python3 /opt/smi-agent/smi_agent.py --dry-run
echo
echo "Próximos passos:"
echo "  1) sudo nano /etc/smi-agent/agent.env      (API, token e id do servidor)"
echo "  2) sudo systemctl enable --now smi-agent"
echo "  3) journalctl -u smi-agent -f               (deve aparecer 'conectado à API')"

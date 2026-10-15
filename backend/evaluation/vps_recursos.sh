#!/usr/bin/env bash
# Mede, NA VPS, o consumo do agente do SMI (e do snmpd, se instalado) usando a contabilidade
# do próprio systemd. Não instala nada e não altera nada: só lê.
#
# Uso:   bash vps_recursos.sh 60        (minutos; padrão 60)
# No fim imprime um JSON: copie e cole para o Claude, ou salve em docs/resultados/dados/vps_recursos.json
set -euo pipefail

MINUTOS="${1:-60}"
INTERVALO=30
SERVICOS=()
for s in smi-agent snmpd; do
  systemctl is-active --quiet "$s" && SERVICOS+=("$s")
done
[ ${#SERVICOS[@]} -eq 0 ] && { echo "nem smi-agent nem snmpd estão rodando" >&2; exit 1; }
NUCLEOS=$(nproc)

cpu_ns() { systemctl show -p CPUUsageNSec --value "$1"; }
mem_b()  { systemctl show -p MemoryCurrent --value "$1"; }

declare -A CPU0 MEMMAX MEMSOMA
for s in "${SERVICOS[@]}"; do CPU0[$s]=$(cpu_ns "$s"); MEMMAX[$s]=0; MEMSOMA[$s]=0; done
INICIO=$(date +%s)
AMOSTRAS=0
echo "medindo ${SERVICOS[*]} por $MINUTOS min (uma amostra a cada $INTERVALO s)…" >&2
while [ $(( $(date +%s) - INICIO )) -lt $(( MINUTOS * 60 )) ]; do
  sleep "$INTERVALO"
  AMOSTRAS=$((AMOSTRAS + 1))
  for s in "${SERVICOS[@]}"; do
    m=$(mem_b "$s")
    MEMSOMA[$s]=$(( MEMSOMA[$s] + m ))
    [ "$m" -gt "${MEMMAX[$s]}" ] && MEMMAX[$s]=$m
  done
done
DUR=$(( $(date +%s) - INICIO ))

echo "{"
echo "  \"teste\": \"vps_recursos\", \"executado_em\": \"$(date -u +%FT%TZ)\", \"minutos\": $((DUR / 60)),"
echo "  \"maquina\": {\"sistema\": \"$(. /etc/os-release; echo "$PRETTY_NAME")\", \"nucleos\": $NUCLEOS, \"ram_mb\": $(free -m | awk '/Mem:/{print $2}')},"
echo "  \"servicos\": {"
i=0
for s in "${SERVICOS[@]}"; do
  i=$((i + 1))
  dcpu=$(( $(cpu_ns "$s") - CPU0[$s] ))
  pct=$(awk -v n="$dcpu" -v d="$DUR" 'BEGIN{printf "%.3f", n / 1e9 / d * 100}')
  pctm=$(awk -v p="$pct" -v c="$NUCLEOS" 'BEGIN{printf "%.4f", p / c}')
  memmed=$(awk -v s="${MEMSOMA[$s]}" -v a="$AMOSTRAS" 'BEGIN{printf "%.1f", s / a / 1048576}')
  memmax=$(awk -v m="${MEMMAX[$s]}" 'BEGIN{printf "%.1f", m / 1048576}')
  sep=$([ $i -lt ${#SERVICOS[@]} ] && echo "," || echo "")
  echo "    \"$s\": {\"cpu_pct_um_nucleo\": $pct, \"cpu_pct_maquina\": $pctm, \"memoria_media_mb\": $memmed, \"memoria_max_mb\": $memmax}$sep"
done
echo "  }"
echo "}"

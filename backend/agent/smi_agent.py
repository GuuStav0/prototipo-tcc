#!/usr/bin/env python3
"""Agente do SMI: lê as métricas desta máquina e envia para a API (POST /ingest/metrics).

Feito para rodar em servidores de produção sem interferir neles:
- só LÊ métricas e faz requisições de SAÍDA; não abre porta nenhuma;
- usa apenas a biblioteca padrão do Python + psutil (no Ubuntu: apt install python3-psutil);
- no systemd roda com usuário próprio sem privilégios, prioridade baixa e limite de CPU/memória
  (ver smi-agent.service).

Se a API estiver fora do ar (ex.: PC do monitoramento desligado), as leituras ficam num buffer
(até ~24 h) e são reenviadas, da mais antiga para a mais nova, quando a API voltar.

Configuração por variáveis de ambiente (no servidor: /etc/smi-agent/agent.env):
    SMI_API_URL        ex.: http://100.101.102.103:8000/api/v1   (obrigatória)
    SMI_INGEST_TOKEN   o mesmo de SMI_INGEST_TOKEN do backend      (obrigatória)
    SMI_HOST_ID        id do servidor cadastrado no SMI, ex.: vps-hostinger (obrigatória)
    SMI_INTERVAL       segundos entre coletas (padrão 15)
    SMI_STATE_DIR      onde guardar o buffer ao desligar (padrão: pasta atual)

Teste sem enviar nada:   python3 smi_agent.py --dry-run
"""

from __future__ import annotations  # compatível com o Python 3.8 do Ubuntu 20.04

import argparse
import json
import logging
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import psutil

VERSION = "1.0"
MAX_BUFFER = 50_000          # ~24 h de leituras a cada 15 s
BATCH_SIZE = 2_000
SKIP_FSTYPES = {"squashfs", "tmpfs", "devtmpfs", "overlay", "iso9660", "udf", "ramfs", "autofs", "proc", "sysfs"}

log = logging.getLogger("smi-agent")


# ---------------------------------------------------------------- coleta
def disk_percent() -> float | None:
    """Uso da partição mais cheia (é ela que indica o risco)."""
    worst = None
    for p in psutil.disk_partitions(all=False):
        if p.fstype.lower() in SKIP_FSTYPES or "cdrom" in p.opts or p.mountpoint.startswith(("/snap", "/boot/efi")):
            continue
        try:
            pct = psutil.disk_usage(p.mountpoint).percent
        except (PermissionError, OSError):
            continue
        worst = pct if worst is None else max(worst, pct)
    return worst


def temperature() -> float | None:
    """Maior temperatura entre os sensores. Máquinas virtuais (VPS) não têm sensores: None."""
    reader = getattr(psutil, "sensors_temperatures", None)
    if reader is None:  # Windows/macOS
        return None
    try:
        sensors = reader()
    except Exception:
        return None
    values = [t.current for entries in sensors.values() for t in entries if t.current and 0 < t.current < 150]
    return max(values) if values else None


def collect() -> list[tuple[str, float]]:
    readings = [
        ("cpu", psutil.cpu_percent(interval=None)),  # média desde a coleta anterior
        ("ram", psutil.virtual_memory().percent),    # usa a memória disponível (desconta cache)
        ("reachable", 1),                            # batimento: "estou vivo"
        ("uptime", int(time.time() - psutil.boot_time())),
    ]
    disk = disk_percent()
    if disk is not None:
        readings.append(("disk", disk))
    temp = temperature()
    if temp is not None:
        readings.append(("temp", temp))
    return [(m, round(float(v), 1) if m != "uptime" else v) for m, v in readings]


# ---------------------------------------------------------------- envio
class Sender:
    def __init__(self, api_url: str, token: str, host_id: str, state_dir: Path, timeout: float = 10):
        self.url = api_url.rstrip("/") + "/ingest/metrics"
        self.token = token
        self.host_id = host_id
        self.timeout = timeout
        self.buffer_file = state_dir / "buffer.json"
        self.buffer: deque[dict] = deque(maxlen=MAX_BUFFER)
        self._load()

    def _load(self) -> None:
        try:
            items = json.loads(self.buffer_file.read_text(encoding="utf-8"))
            self.buffer.extend(items)
            self.buffer_file.unlink()
            log.info("buffer recuperado do disco: %d leituras pendentes", len(items))
        except FileNotFoundError:
            pass
        except Exception as exc:
            log.warning("buffer em disco ilegível, descartado: %s", exc)

    def save(self) -> None:
        if not self.buffer:
            return
        try:
            self.buffer_file.parent.mkdir(parents=True, exist_ok=True)
            self.buffer_file.write_text(json.dumps(list(self.buffer)), encoding="utf-8")
            log.info("buffer salvo em disco: %d leituras", len(self.buffer))
        except Exception as exc:
            log.warning("não foi possível salvar o buffer: %s", exc)

    def add(self, readings: list[tuple[str, float]], at: datetime) -> None:
        dropped = max(0, len(self.buffer) + len(readings) - MAX_BUFFER)
        if dropped:
            log.warning("buffer cheio: descartando as %d leituras mais antigas", dropped)
        ts = at.isoformat()
        self.buffer.extend({"host_id": self.host_id, "metric": m, "value": v, "collected_at": ts} for m, v in readings)

    def _post(self, samples: list[dict]) -> dict:
        body = json.dumps({"source": "agent", "collector_id": f"smi-agent/{VERSION}", "samples": samples}).encode()
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Content-Type": "application/json", "X-Ingest-Token": self.token})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read() or b"{}")

    def flush(self) -> bool:
        """Envia o buffer (mais antigo primeiro). Devolve True se esvaziou."""
        while self.buffer:
            batch = [self.buffer[i] for i in range(min(BATCH_SIZE, len(self.buffer)))]
            try:
                result = self._post(batch)
            except urllib.error.HTTPError as exc:
                detail = exc.read()[:300].decode(errors="replace")
                if exc.code == 401:
                    log.error("token recusado pela API (confira SMI_INGEST_TOKEN): %s", detail)
                elif 400 <= exc.code < 500:
                    # lote inválido não adianta reenviar
                    log.error("API recusou o lote (%d): %s; %d leituras descartadas", exc.code, detail, len(batch))
                    for _ in batch:
                        self.buffer.popleft()
                    continue
                else:
                    log.warning("API respondeu %d; tentando de novo no próximo ciclo", exc.code)
                return False
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                log.warning("API inacessível (%s); %d leituras no buffer", getattr(exc, "reason", exc), len(self.buffer))
                return False
            for _ in batch:
                self.buffer.popleft()
            for r in result.get("rejected", [])[:3]:
                log.warning("leitura recusada: %s", r.get("reason"))
            if len(batch) > 50:
                log.info("%d leituras pendentes enviadas", len(batch))
        return True


# ---------------------------------------------------------------- principal
def main() -> None:
    parser = argparse.ArgumentParser(description="Agente do SMI")
    parser.add_argument("--dry-run", action="store_true", help="só mostra uma coleta, sem enviar")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)

    psutil.cpu_percent(interval=None)  # a primeira medição de CPU sempre vem zerada
    if args.dry_run:
        time.sleep(1)
        print(json.dumps(dict(collect()), indent=2))
        return

    env = os.environ
    missing = [k for k in ("SMI_API_URL", "SMI_INGEST_TOKEN", "SMI_HOST_ID") if not env.get(k)]
    if missing:
        sys.exit(f"faltam variáveis de ambiente: {', '.join(missing)}")
    interval = int(env.get("SMI_INTERVAL", "15"))
    state_dir = Path(env.get("SMI_STATE_DIR") or env.get("STATE_DIRECTORY") or ".")
    sender = Sender(env["SMI_API_URL"], env["SMI_INGEST_TOKEN"], env["SMI_HOST_ID"], state_dir)

    try:
        os.nice(10)  # nunca disputa CPU com os serviços do servidor
    except (AttributeError, OSError):
        pass

    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("SMI agent %s: host=%s, api=%s, a cada %d s", VERSION, env["SMI_HOST_ID"], sender.url, interval)

    online = None
    next_run = time.monotonic()
    while running:
        sender.add(collect(), datetime.now(timezone.utc))
        ok = sender.flush()
        if ok != online:
            log.info("conectado à API" if ok else "sem conexão com a API; guardando leituras")
            online = ok
        next_run += interval
        while running and time.monotonic() < next_run:
            time.sleep(0.5)
        if time.monotonic() - next_run > interval:  # o sistema ficou suspenso: não acumula ciclos
            next_run = time.monotonic()

    sender.save()
    log.info("agente encerrado")


if __name__ == "__main__":
    main()

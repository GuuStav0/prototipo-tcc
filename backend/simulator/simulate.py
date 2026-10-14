"""Coletor simulado do SMI.

Gera leituras de CPU, memória, disco, temperatura, alcance e uptime para os servidores em
modo "simulado" e envia para POST /ingest/metrics. Servidores em modo "real" são ignorados:
os dados deles vêm do agente (agent/smi_agent.py) ou do coletor SNMP (collector/snmp_poller.py).

Uso:
  python simulator/simulate.py                    # coleta ao vivo a cada 15 s
  python simulator/simulate.py --backfill 24h     # gera histórico das últimas 24 h e segue ao vivo
  python simulator/simulate.py --backfill 24h --once   # só o histórico

Injeção de falhas (para testar gatilhos e medir o tempo de detecção, TCC 4.5):
  edite simulator/faults.json enquanto o simulador roda, por exemplo
    [ {"host": "srv-web-01", "metric": "cpu", "value": 97},
      {"host": "srv-mail-01", "metric": "reachable", "value": 0} ]
  A falha vale enquanto estiver no arquivo. O início e o fim de cada falha são registrados
  em simulator/faults-log.csv para comparar com o started_at do alerta.
"""

import argparse
import csv
import json
import math
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).parent
DEFAULT_FAULTS = HERE / "faults.json"
FAULT_LOG = HERE / "faults-log.csv"

# Valores de referência por host (os mesmos do mock do front-end). Hosts sem perfil
# recebem valores "saudáveis" aleatórios.
PROFILES = {
    "srv-web-01": dict(cpu=34, ram=52, disk=61, temp=46),
    "srv-web-02": dict(cpu=29, ram=48, disk=58, temp=44),
    "srv-db-01": dict(cpu=70, ram=84, disk=71, temp=58),
    "srv-db-02": dict(cpu=41, ram=63, disk=55, temp=49),
    "srv-app-01": dict(cpu=37, ram=55, disk=40, temp=45),
    "srv-app-02": dict(cpu=96, ram=91, disk=88, temp=79),
    "srv-cache-01": dict(cpu=22, ram=38, disk=25, temp=41),
    "srv-backup-01": dict(cpu=65, ram=72, disk=93, temp=55),
    "srv-mail-01": dict(cpu=30, ram=44, disk=62, temp=43),
    "srv-monitor-01": dict(cpu=26, ram=40, disk=35, temp=42),
}
NOISE = dict(cpu=4.0, ram=1.5, disk=0.05, temp=1.0)
PULL = dict(cpu=0.35, ram=0.2, disk=0.05, temp=0.3)  # força de volta ao valor de referência


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class HostModel:
    """Passeio aleatório que tende ao valor de referência, com ciclo diário na CPU."""

    def __init__(self, host_id: str, rng: random.Random):
        self.rng = rng
        self.base = PROFILES.get(host_id) or dict(
            cpu=rng.uniform(15, 45), ram=rng.uniform(30, 60),
            disk=rng.uniform(20, 70), temp=rng.uniform(38, 50))
        self.value = dict(self.base)
        self.boot = datetime.now(timezone.utc) - timedelta(days=rng.uniform(5, 200))
        self.spike_until: datetime | None = None
        self.spike_metric = "cpu"

    def maybe_spike(self, at: datetime, chance: float):
        """Episódios aleatórios de sobrecarga (só no histórico, por padrão)."""
        if self.spike_until and at < self.spike_until:
            return
        self.spike_until = None
        if self.rng.random() < chance:
            self.spike_metric = self.rng.choice(["cpu", "cpu", "ram", "temp"])
            self.spike_until = at + timedelta(minutes=self.rng.uniform(10, 40))

    def step(self, at: datetime) -> dict[str, float]:
        hour = at.hour + at.minute / 60
        daily = 8 * math.sin((hour - 9) / 24 * 2 * math.pi)  # pico de uso à tarde
        for m in ("cpu", "ram", "disk", "temp"):
            target = self.base[m] + (daily if m == "cpu" else 0)
            if self.spike_until and m == self.spike_metric:
                target = {"cpu": 95, "ram": 93, "temp": 78}[m]
            v = self.value[m]
            v += PULL[m] * (target - v) + self.rng.gauss(0, NOISE[m])
            self.value[m] = v
        # temperatura acompanha a CPU
        temp = self.value["temp"] + (self.value["cpu"] - self.base["cpu"]) * 0.15
        return {
            "cpu": round(clamp(self.value["cpu"], 0, 100), 1),
            "ram": round(clamp(self.value["ram"], 0, 100), 1),
            "disk": round(clamp(self.value["disk"], 0, 100), 1),
            "temp": round(clamp(temp, 20, 110), 1),
        }


class Simulator:
    def __init__(self, api: str, token: str, faults_path: Path, seed: int | None):
        self.client = httpx.Client(base_url=api.rstrip("/"), headers={"X-Ingest-Token": token}, timeout=30)
        self.faults_path = faults_path
        self.rng = random.Random(seed)
        self.models: dict[str, HostModel] = {}
        self.active_faults: set[tuple[str, str]] = set()

    # ------------------------------------------------------------ API
    def hosts(self) -> list[str]:
        """Só os servidores em modo simulado: os reais recebem dados do agente ou do SNMP."""
        r = self.client.get("/servers", params={"mode": "simulated"})
        r.raise_for_status()
        return [s["id"] for s in r.json()["items"] if s["enabled"] and s.get("mode", "simulated") == "simulated"]

    def send(self, samples: list[dict]) -> None:
        for i in range(0, len(samples), 5000):
            r = self.client.post("/ingest/metrics", json={
                "source": "simulator", "collector_id": "simulator", "samples": samples[i:i + 5000]})
            if r.status_code != 202:
                raise RuntimeError(f"ingestão falhou ({r.status_code}): {r.text}")
            rejected = r.json()["rejected"]
            if rejected:
                print(f"  {len(rejected)} leitura(s) rejeitada(s), ex.: {rejected[0]['reason']}")

    # ------------------------------------------------------------ falhas
    def load_faults(self) -> dict[tuple[str, str], float]:
        if not self.faults_path.exists():
            return {}
        try:
            data = json.loads(self.faults_path.read_text(encoding="utf-8") or "[]")
            return {(f["host"], f["metric"]): float(f["value"]) for f in data}
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            print(f"  faults.json inválido, ignorando: {exc}")
            return {}

    def log_fault_changes(self, faults: dict, at: datetime) -> None:
        current = set(faults)
        new_file = not FAULT_LOG.exists()
        with FAULT_LOG.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["event", "host", "metric", "value", "at"])
            for host, metric in sorted(current - self.active_faults):
                w.writerow(["start", host, metric, faults[(host, metric)], at.isoformat()])
                print(f"  FALHA INICIADA  {host} {metric}={faults[(host, metric)]} em {at:%H:%M:%S}")
            for host, metric in sorted(self.active_faults - current):
                w.writerow(["end", host, metric, "", at.isoformat()])
                print(f"  falha encerrada {host} {metric} em {at:%H:%M:%S}")
        self.active_faults = current

    # ------------------------------------------------------------ leituras
    def readings(self, hosts: list[str], at: datetime, faults: dict, spike_chance: float) -> list[dict]:
        ts = at.isoformat()
        samples = []
        for host in hosts:
            model = self.models.setdefault(host, HostModel(host, self.rng))
            if faults.get((host, "reachable")) == 0:
                samples.append(dict(host_id=host, metric="reachable", value=0, collected_at=ts))
                continue
            model.maybe_spike(at, spike_chance)
            values = model.step(at)
            for metric, value in values.items():
                if (host, metric) in faults:
                    value = round(faults[(host, metric)] + self.rng.uniform(-0.5, 0.5), 1)
                samples.append(dict(host_id=host, metric=metric, value=value, collected_at=ts))
            samples.append(dict(host_id=host, metric="reachable", value=1, collected_at=ts))
            uptime = int((at - model.boot).total_seconds())
            samples.append(dict(host_id=host, metric="uptime", value=max(uptime, 0), collected_at=ts))
        return samples

    def backfill(self, span: timedelta, step: int) -> None:
        hosts = self.hosts()
        now = datetime.now(timezone.utc).replace(microsecond=0)
        at = now - span
        batch: list[dict] = []
        print(f"Gerando histórico de {span} para {len(hosts)} servidores (1 leitura a cada {step} s)...")
        while at < now:
            batch += self.readings(hosts, at, {}, spike_chance=0.004)
            if len(batch) >= 4000:
                self.send(batch)
                batch = []
            at += timedelta(seconds=step)
        if batch:
            self.send(batch)
        print("Histórico enviado.")

    def live(self, interval: int, spike_chance: float) -> None:
        print(f"Coleta ao vivo a cada {interval} s (Ctrl+C para parar). Falhas: {self.faults_path}")
        while True:
            started = time.monotonic()
            at = datetime.now(timezone.utc).replace(microsecond=0)
            try:
                hosts = self.hosts()
                faults = self.load_faults()
                self.log_fault_changes(faults, at)
                samples = self.readings(hosts, at, faults, spike_chance)
                self.send(samples)
                print(f"{at:%H:%M:%S}  {len(samples)} leituras de {len(hosts)} servidores")
            except (httpx.HTTPError, RuntimeError) as exc:
                print(f"{at:%H:%M:%S}  erro: {exc}")
            time.sleep(max(0.0, interval - (time.monotonic() - started)))


def default_token() -> str:
    """O mesmo token da API (lido do backend/.env), para não precisar repetir na linha de comando."""
    try:
        sys.path.insert(0, str(HERE.parent))
        from app.config import get_settings

        return get_settings().ingest_token
    except Exception:
        return "dev-token"


def parse_span(text: str) -> timedelta:
    units = {"h": 3600, "d": 86400, "m": 60}
    if not text or text[-1] not in units or not text[:-1].isdigit():
        raise argparse.ArgumentTypeError("use algo como 30m, 24h ou 7d")
    return timedelta(seconds=int(text[:-1]) * units[text[-1]])


def main() -> None:
    p = argparse.ArgumentParser(description="Coletor simulado do SMI")
    p.add_argument("--api", default="http://127.0.0.1:8000/api/v1")
    p.add_argument("--token", default=default_token(),
                   help="padrão: o SMI_INGEST_TOKEN do backend/.env")
    p.add_argument("--interval", type=int, default=15, help="segundos entre coletas (padrão 15)")
    p.add_argument("--backfill", type=parse_span, help="gera histórico antes de começar (ex. 24h)")
    p.add_argument("--backfill-step", type=int, default=300, help="segundos entre leituras do histórico")
    p.add_argument("--once", action="store_true", help="só gera o histórico e sai")
    p.add_argument("--random-spikes", action="store_true", help="sobrecargas aleatórias também ao vivo")
    p.add_argument("--faults", type=Path, default=DEFAULT_FAULTS)
    p.add_argument("--seed", type=int, help="semente para resultados reproduzíveis")
    args = p.parse_args()

    sim = Simulator(args.api, args.token, args.faults, args.seed)
    try:
        if args.backfill:
            sim.backfill(args.backfill, args.backfill_step)
        if not args.once:
            sim.live(args.interval, 0.002 if args.random_spikes else 0.0)
    except httpx.ConnectError:
        sys.exit(f"Não consegui conectar em {args.api}. O backend está rodando?")
    except KeyboardInterrupt:
        print("\nSimulador encerrado.")


if __name__ == "__main__":
    main()

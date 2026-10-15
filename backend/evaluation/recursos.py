"""Teste de consumo de recursos dos coletores (TCC 4.5: < 5% de CPU e < 256 MB em regime contínuo).

Dois modos:
  .venv\\Scripts\\python -m evaluation.recursos                     # agente rodando aqui, 10 min
  .venv\\Scripts\\python -m evaluation.recursos --anexar snmp_poller --minutos 30
       (mede um processo que já está rodando, achado pela linha de comando; ex.: o coletor SNMP)

Na VPS, o consumo do agente é medido pelo próprio systemd: evaluation/vps_recursos.sh.

CPU é informada como % de UM núcleo (a forma mais exigente) e como % da máquina inteira.
"""

import argparse
import os
import subprocess
import sys
import time

import psutil

from .ambiente import Ambiente, _matar_arvore
from .comum import BACKEND_DIR, resumo, salvar

META_CPU, META_MEM = 5.0, 256.0


def amostrar(proc: psutil.Process, minutos: float, intervalo: float = 2.0) -> dict:
    nucleos = psutil.cpu_count()
    cpu, mem = [], []
    proc.cpu_percent(None)
    fim = time.time() + minutos * 60
    while time.time() < fim:
        time.sleep(intervalo)
        try:
            cpu.append(proc.cpu_percent(None))
            mem.append(proc.memory_info().rss / 2**20)
        except psutil.NoSuchProcess:
            break
    tempo_cpu = sum(cpu) / 100 * intervalo
    r = {
        "minutos": round(len(cpu) * intervalo / 60, 1),
        "cpu_pct_um_nucleo": resumo(cpu, 2),
        "cpu_pct_maquina_media": round(sum(cpu) / len(cpu) / nucleos, 3) if cpu else None,
        "tempo_cpu_s": round(tempo_cpu, 2),
        "memoria_mb": resumo(mem),
        "nucleos": nucleos,
    }
    r["atingiu_meta"] = bool(cpu) and r["cpu_pct_um_nucleo"]["media"] < META_CPU and r["memoria_mb"]["max"] < META_MEM
    return r


def anexar(padrao: str, minutos: float) -> None:
    alvos = [p for p in psutil.process_iter(["pid", "cmdline"])
             if p.info["cmdline"] and padrao in " ".join(p.info["cmdline"]) and p.pid != os.getpid()]
    if not alvos:
        sys.exit(f"nenhum processo rodando com '{padrao}' na linha de comando")
    proc = max(alvos, key=lambda p: p.memory_info().rss)  # o processo Python de verdade (não o lançador)
    print(f"medindo PID {proc.pid} ({' '.join(proc.cmdline())[:80]}) por {minutos} min…")
    r = amostrar(proc, minutos)
    imprimir(padrao, r)
    salvar(f"recursos_{padrao.replace('.', '_')}", {"processo": padrao, "meta": "< 5% CPU e < 256 MB", **r})


def agente_local(minutos: float) -> None:
    with Ambiente() as amb:
        amb.api.post("servers", json={"id": "agente-local", "name": "agente-local", "address": "127.0.0.1",
                                      "agent": {"enabled": True}, "snmp": {"enabled": False}}).raise_for_status()
        env = {**os.environ, "SMI_API_URL": amb.api_url, "SMI_INGEST_TOKEN": amb.token,
               "SMI_HOST_ID": "agente-local", "SMI_STATE_DIR": str(amb.dir), "PYTHONIOENCODING": "utf-8"}
        log = open(amb.dir / "agente.log", "w", encoding="utf-8")
        proc = subprocess.Popen([sys.executable, "agent/smi_agent.py"], cwd=BACKEND_DIR, env=env,
                                stdout=log, stderr=subprocess.STDOUT)
        try:
            time.sleep(5)
            # no Windows o python.exe do venv é um lançador: o agente de verdade é o processo filho
            pai = psutil.Process(proc.pid)
            real = max([pai, *pai.children(recursive=True)], key=lambda p: p.memory_info().rss)
            print(f"medindo o agente (PID {real.pid}) por {minutos} min…")
            r = amostrar(real, minutos)
            recebidas = amb.api.get("servers/agente-local/metrics", params={"metric": "cpu", "range": "1h", "step": 15}).json()
            r["leituras_de_cpu_recebidas"] = sum(1 for p in recebidas["items"][0]["points"] if p["v"] is not None)
        finally:
            _matar_arvore(proc)
            log.close()
    imprimir("agente (smi_agent.py)", r)
    salvar("recursos_agente", {"processo": "agent/smi_agent.py nesta máquina", "meta": "< 5% CPU e < 256 MB", **r})


def imprimir(nome: str, r: dict) -> None:
    c, m = r["cpu_pct_um_nucleo"], r["memoria_mb"]
    print(f"\n{nome}: CPU média {c['media']}% de um núcleo (máx {c['max']}%), {r['cpu_pct_maquina_media']}% da máquina;"
          f" memória média {m['media']} MB (máx {m['max']} MB) -> {'dentro' if r['atingiu_meta'] else 'FORA'} da meta")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anexar", metavar="TRECHO_DA_LINHA_DE_COMANDO")
    ap.add_argument("--minutos", type=float, default=10)
    a = ap.parse_args()
    if a.anexar:
        anexar(a.anexar, a.minutos)
    else:
        agente_local(a.minutos)


if __name__ == "__main__":
    main()

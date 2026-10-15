"""Teste de carga e estresse (TCC 4.4).

Simula N servidores enviando leituras ao mesmo tempo, como N agentes, a cada 15 s, e aumenta N
por etapas até o sistema não dar conta. Em cada etapa mede:
- tempo de cada envio (ingestão) e erros;
- se o ciclo inteiro termina dentro dos 15 s (senão o sistema começa a atrasar);
- o tempo de resposta do dashboard durante a carga (GET /overview e GET /servers);
- CPU e memória do processo da API.

Uso (na pasta backend):  .venv\\Scripts\\python -m evaluation.carga
"""

import asyncio
import random
import threading
import time
from datetime import datetime, timezone

import httpx
import psutil

from .ambiente import Ambiente
from .comum import resumo, salvar

NIVEIS = [10, 50, 100, 250, 500, 1000]
CICLOS = 4
INTERVALO = 15
LIMITES = {"ciclo_s": INTERVALO, "dashboard_p95_ms": 2000, "erros": 0}


class Amostrador(threading.Thread):
    """CPU (% de um núcleo) e memória do processo da API, a cada 1 s."""

    def __init__(self, proc: psutil.Process):
        super().__init__(daemon=True)
        self.proc, self.cpu, self.mem, self.parar = proc, [], [], threading.Event()
        proc.cpu_percent(None)

    def run(self):
        while not self.parar.wait(1):
            self.cpu.append(self.proc.cpu_percent(None))
            self.mem.append(self.proc.memory_info().rss / 2**20)


async def ciclo(cliente: httpx.AsyncClient, hosts: list[str], rnd: random.Random) -> tuple[list[float], int, float]:
    at = datetime.now(timezone.utc).isoformat()

    async def enviar(h):
        amostras = [{"host_id": h, "metric": m, "value": round(rnd.uniform(10, 70), 1), "collected_at": at}
                    for m in ("cpu", "ram", "disk", "temp")]
        amostras += [{"host_id": h, "metric": "reachable", "value": 1, "collected_at": at},
                     {"host_id": h, "metric": "uptime", "value": 86400, "collected_at": at}]
        t0 = time.perf_counter()
        try:
            r = await cliente.post("ingest/metrics", json={"source": "simulator", "samples": amostras})
            ok = r.status_code == 202 and not r.json()["rejected"]
        except httpx.HTTPError:
            ok = False
        return (time.perf_counter() - t0) * 1000, ok

    t0 = time.perf_counter()
    resultados = await asyncio.gather(*(enviar(h) for h in hosts))
    return [ms for ms, _ in resultados], sum(1 for _, ok in resultados if not ok), time.perf_counter() - t0


async def sonda_dashboard(cliente: httpx.AsyncClient, parar: asyncio.Event, tempos: list[float]):
    while not parar.is_set():
        for rota in ("overview", "servers"):
            t0 = time.perf_counter()
            try:
                (await cliente.get(rota)).raise_for_status()
                tempos.append((time.perf_counter() - t0) * 1000)
            except httpx.HTTPError:
                tempos.append(float("inf"))
        await asyncio.sleep(1)


async def nivel(amb: Ambiente, n: int, rnd: random.Random) -> dict:
    hosts = [f"carga-{i:04d}" for i in range(n)]
    limites = httpx.Limits(max_connections=n + 10, max_keepalive_connections=n + 10)
    async with httpx.AsyncClient(base_url=amb.api_url + "/", timeout=120, limits=limites,
                                 headers={"X-Ingest-Token": amb.token}) as cliente:
        # cadastra os servidores que faltam
        existentes = {s["id"] for s in (await cliente.get("servers")).json()["items"]}
        for h in hosts:
            if h not in existentes:
                await cliente.post("servers", json={"id": h, "name": h, "address": "10.9.0.1", "mode": "simulated"})

        amostrador = Amostrador(amb.processo("api"))
        amostrador.start()
        parar, dashboard = asyncio.Event(), []
        sonda = asyncio.create_task(sonda_dashboard(cliente, parar, dashboard))
        envios, erros, ciclos = [], 0, []
        for _ in range(CICLOS):
            inicio = time.perf_counter()
            ms, e, dur = await ciclo(cliente, hosts, rnd)
            envios += ms
            erros += e
            ciclos.append(dur)
            await asyncio.sleep(max(0.0, INTERVALO - (time.perf_counter() - inicio)))
        parar.set()
        await sonda
        amostrador.parar.set()
        amostrador.join()

    finitos = [t for t in dashboard if t != float("inf")]
    r = {
        "servidores": n,
        "leituras_por_ciclo": n * 6,
        "envio_ms": resumo(envios),
        "erros": erros,
        "ciclo_s": resumo(ciclos, 2),
        "dashboard_ms": resumo(finitos),
        "dashboard_falhas": len(dashboard) - len(finitos),
        "api_cpu_pct_um_nucleo": resumo(amostrador.cpu),
        "api_memoria_mb": resumo(amostrador.mem),
    }
    r["dentro_dos_limites"] = (r["ciclo_s"]["max"] < LIMITES["ciclo_s"] and erros == 0
                               and r["dashboard_falhas"] == 0
                               and (r["dashboard_ms"].get("p95") or 0) < LIMITES["dashboard_p95_ms"])
    return r


def main() -> None:
    rnd = random.Random(3)
    niveis = []
    with Ambiente() as amb:
        for n in NIVEIS:
            print(f"\n{n} servidores enviando a cada {INTERVALO} s ({CICLOS} ciclos)…", flush=True)
            r = asyncio.run(nivel(amb, n, rnd))
            niveis.append(r)
            print(f"  envio: mediana {r['envio_ms']['mediana']} ms, p95 {r['envio_ms']['p95']} ms | erros {r['erros']}"
                  f" | ciclo máx {r['ciclo_s']['max']} s | dashboard p95 {r['dashboard_ms'].get('p95')} ms"
                  f" | API CPU média {r['api_cpu_pct_um_nucleo']['media']}% | memória máx {r['api_memoria_mb']['max']} MB"
                  f" | {'OK' if r['dentro_dos_limites'] else 'LIMITE ULTRAPASSADO'}", flush=True)
            if not r["dentro_dos_limites"] and r["ciclo_s"]["max"] > 2 * INTERVALO:
                print("  sistema saturado; níveis maiores não fariam sentido")
                break

    suportado = max((r["servidores"] for r in niveis if r["dentro_dos_limites"]), default=0)
    print(f"\nmaior carga dentro dos limites: {suportado} servidores")
    salvar("carga", {
        "metodo": f"N servidores simulados enviando 6 leituras cada, todos ao mesmo tempo, a cada {INTERVALO} s; "
                  "API com 1 processo, banco SQLite; o dashboard é consultado a cada 1 s durante a carga",
        "limites": LIMITES,
        "niveis": niveis,
        "maior_carga_suportada": suportado,
    })


if __name__ == "__main__":
    main()

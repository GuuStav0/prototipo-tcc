"""Regressão: muitos coletores enviando ao mesmo tempo (achado no teste de carga da etapa 6).

Antes da correção, cada envio usava duas conexões do banco ao mesmo tempo; com dezenas de
envios simultâneos, o pool esgotava e a API travava por 30 s (deadlock).
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from conftest import TOKEN

API = "/api/v1"


def test_many_simultaneous_ingests(client):
    hosts = [f"carga-{i:02d}" for i in range(40)]
    for h in hosts:
        client.post(f"{API}/servers", json={"id": h, "name": h, "address": "10.0.0.1", "mode": "simulated"})
    at = datetime.now(timezone.utc).isoformat()

    def enviar(h):
        r = client.post(f"{API}/ingest/metrics", headers=TOKEN, json={"source": "simulator", "samples": [
            {"host_id": h, "metric": m, "value": 50, "collected_at": at} for m in ("cpu", "ram", "disk", "temp", "reachable")
        ][:4] + [{"host_id": h, "metric": "reachable", "value": 1, "collected_at": at}]})
        return r.status_code, r.json().get("accepted")

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=40) as pool:
        resultados = list(pool.map(enviar, hosts))
    assert all(r == (202, 5) for r in resultados), resultados
    assert time.perf_counter() - t0 < 15  # antes da correção: ~30 s e erros
    # o dashboard continua respondendo e vê todos os servidores
    servidores = client.get(f"{API}/servers").json()["items"]
    assert sum(1 for s in servidores if s["id"].startswith("carga-") and s["last_seen_at"]) == 40

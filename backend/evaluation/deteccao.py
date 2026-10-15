"""Teste do tempo de detecção de falhas (TCC 4.5: < 90 s).

Mede o tempo entre o INÍCIO de uma condição de erro e a EXIBIÇÃO do alerta no dashboard,
como o usuário vê: o painel fica aberto num navegador real (Edge, build de produção) na tela
de Gatilhos, que se atualiza sozinha a cada 10 s, e o teste cronometra até a linha do alerta
aparecer.

Cada tentativa injeta uma falha num servidor saudável (CPU, memória, disco, temperatura ou
queda do servidor) pelo coletor simulado. O tempo total é dividido em:
  espera da coleta  -> do início da falha até a primeira leitura com a falha (até 15 s)
  confirmação       -> duração exigida pelo gatilho (60 s; queda: 45 s)
  exibição          -> do disparo do alerta até ele aparecer na tela (até 10 s)
Também mede o tempo até o alerta RESOLVER depois que a falha termina.

Uso (na pasta backend):  .venv\\Scripts\\python -m evaluation.deteccao [tentativas]
"""

import csv
import random
import sys
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

from .ambiente import Ambiente
from .comum import parse_iso, resumo, salvar

SAUDAVEIS = ["srv-web-01", "srv-web-02", "srv-cache-01", "srv-mail-01", "srv-monitor-01", "srv-app-01", "srv-db-02"]
FALHAS = {
    "cpu": (97, "CPU elevada"),
    "ram": (95, "Memória elevada"),
    "disk": (97, "Disco quase cheio"),
    "temp": (85, "Temperatura elevada"),
    "reachable": (0, "Host inalcançável"),
}
META_S = 90


def agora() -> datetime:
    return datetime.now(timezone.utc)


def inicio_registrado(amb: Ambiente, host: str, metric: str) -> datetime | None:
    """Horário da primeira leitura com a falha, registrado pelo simulador (faults-log.csv)."""
    log = amb.arquivo_falhas.with_name("faults-log.csv")
    if not log.exists():
        return None
    with log.open(encoding="utf-8") as f:
        linhas = [r for r in csv.DictReader(f) if r["event"] == "start" and r["host"] == host and r["metric"] == metric]
    return parse_iso(linhas[-1]["at"]) if linhas else None


def main() -> None:
    tentativas = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    rnd = random.Random(7)
    combos = [(h, m) for m in FALHAS for h in SAUDAVEIS]
    rnd.shuffle(combos)
    combos = combos[:tentativas]

    resultados = []
    with Ambiente(simulador=True, painel=True) as amb, sync_playwright() as pw:
        navegador = pw.chromium.launch(channel="msedge", headless=True)
        pagina = navegador.new_page(viewport={"width": 1400, "height": 900})
        time.sleep(20)  # coletas normais antes da primeira falha
        pagina.goto(f"{amb.painel_url}/gatilhos", wait_until="networkidle")

        for n, (host, metric) in enumerate(combos, 1):
            valor, gatilho = FALHAS[metric]
            time.sleep(rnd.uniform(0, 15))  # fase aleatória em relação ao ciclo de coleta
            t_inicio = agora()
            amb.injetar([{"host": host, "metric": metric, "value": valor}])

            linha = pagina.locator(f'tr:has-text("{host}"):has-text("{gatilho}")')
            linha.first.wait_for(state="visible", timeout=180_000)
            t_tela = agora()
            amb.injetar([])  # a falha termina assim que é vista
            t_fim_falha = agora()

            alerta = amb.api.get("alerts", params={"host_id": host, "status": "active", "limit": 5}).json()["items"]
            alerta = next(a for a in alerta if a["metric"] == metric)
            t_coleta = inicio_registrado(amb, host, metric) or parse_iso(alerta["first_breach_at"])
            disparo = parse_iso(alerta["started_at"])
            r = {
                "host": host, "metrica": metric, "gatilho": gatilho, "alerta_id": alerta["id"],
                "inicio_falha": t_inicio.isoformat(), "fim_falha": t_fim_falha.isoformat(),
                "espera_coleta_s": round(max(0.0, (t_coleta - t_inicio).total_seconds()), 1),
                "confirmacao_s": round((disparo - parse_iso(alerta["first_breach_at"])).total_seconds(), 1),
                "exibicao_s": round((t_tela - disparo).total_seconds(), 1),
                "total_s": round((t_tela - t_inicio).total_seconds(), 1),
            }
            resultados.append(r)
            print(f"[{n}/{len(combos)}] {host:15} {metric:9} total {r['total_s']:5.1f} s "
                  f"(coleta {r['espera_coleta_s']:4.1f} + confirmação {r['confirmacao_s']:4.1f} "
                  f"+ exibição {r['exibicao_s']:4.1f})", flush=True)

        # tempo até resolver, depois que a falha termina
        print("aguardando as resoluções…")
        prazo = time.time() + 180
        pendentes = {r["alerta_id"]: r for r in resultados}
        while pendentes and time.time() < prazo:
            for aid in list(pendentes):
                a = amb.api.get(f"alerts/{aid}").json()
                if a["status"] == "resolved":
                    r = pendentes.pop(aid)
                    r["resolucao_s"] = round((parse_iso(a["resolved_at"]) - parse_iso(r["fim_falha"])).total_seconds(), 1)
            time.sleep(3)
        navegador.close()

    totais = [r["total_s"] for r in resultados]
    acima = [r for r in resultados if r["total_s"] >= META_S]
    print(f"\ntempo de detecção: média {sum(totais) / len(totais):.1f} s, máximo {max(totais):.1f} s, "
          f"{len(acima)} de {len(totais)} acima de {META_S} s")
    salvar("deteccao", {
        "meta": f"< {META_S} s entre o início da falha e a exibição do alerta no dashboard",
        "metodo": "falha injetada pelo coletor simulado; cronômetro até a linha do alerta aparecer na tela "
                  "de Gatilhos do painel aberto no Microsoft Edge (build de produção, atualização a cada 10 s)",
        "total_s": resumo(totais),
        "espera_coleta_s": resumo([r["espera_coleta_s"] for r in resultados]),
        "confirmacao_s": resumo([r["confirmacao_s"] for r in resultados]),
        "exibicao_s": resumo([r["exibicao_s"] for r in resultados]),
        "resolucao_s": resumo([r["resolucao_s"] for r in resultados if "resolucao_s" in r]),
        "por_metrica": {m: resumo([r["total_s"] for r in resultados if r["metrica"] == m]) for m in FALHAS},
        "tentativas": resultados,
        "atingiu_meta": not acima,
    })


if __name__ == "__main__":
    main()

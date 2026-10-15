"""Teste de integração com a IA (TCC 4.4 e 5.5).

Faz ao assistente perguntas cuja resposta certa o próprio sistema conhece e confere cada
resposta automaticamente contra a API (consultada logo depois da resposta):
  - acertou o servidor / a quantidade / o valor?
  - usou a ferramenta MCP adequada?
  - inventou algum servidor que não existe? (alucinação)
Cada pergunta é feita REPETICOES vezes, em conversas novas, porque o modelo varia.
Mede também o tempo de resposta e a geração de relatório com análise da IA.

Usa o provedor configurado (padrão: Ollama local com qwen2.5:7b; o Ollama precisa estar aberto).
Uso (na pasta backend):  .venv\\Scripts\\python -m evaluation.ia
"""

import os
import re
import time

from .ambiente import Ambiente
from .comum import resumo, salvar

REPETICOES = 3
SERVIDORES_VALIDOS = None  # preenchido com a lista da API


def numeros(texto: str) -> list[float]:
    return [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", texto)]


def servidores_citados(texto: str) -> set[str]:
    return set(re.findall(r"srv-[a-z0-9-]+[a-z0-9]", texto.lower()))


def estado(api) -> dict:
    servidores = api.get("servers").json()["items"]
    ordem = {"critical": 0, "warning": 1, "ok": 2, "unknown": 3}
    pior = sorted(servidores, key=lambda s: (ordem[s["status"]], -s["active_alerts"]["critical"]))[0]
    return {
        "servidores": servidores,
        "por_id": {s["id"]: s for s in servidores},
        "pior": pior["id"],
        "criticos": [s["id"] for s in servidores if s["status"] == "critical"],
        "avisos": [s["id"] for s in servidores if s["status"] == "warning"],
    }


NUM_PT = {0: ("0", "nenhum", "zero"), 1: ("1", "um", "uma", "único"), 2: ("2", "dois", "duas"), 3: ("3", "três")}


def contagem_ok(resposta: str, esperado: int) -> bool:
    """O número tem de vir junto da palavra servidor ("1 servidor", "um servidor", "apenas um servidor")."""
    palavras = "|".join(NUM_PT.get(esperado, (str(esperado),)))
    return re.search(rf"(?<![\w-])({palavras})\s+(?:\w+\s+)?servidor", resposta.lower()) is not None


def sem_alertas_ok(resposta: str) -> bool:
    r = resposta.lower()
    return any(x in r for x in ("não há", "não existe", "não possui", "nenhum alerta", "não tem"))

# (pergunta, ferramentas aceitas, verificação(resposta, estado, api) -> (ok, detalhe))
PERGUNTAS = [
    ("Qual servidor está em pior estado e por quê?",
     {"get_overview", "list_servers"},
     lambda r, e, api: (e["pior"] in r.lower(), f"esperado {e['pior']}")),
    ("Quantos servidores estão em estado crítico agora?",
     {"get_overview", "list_servers"},
     lambda r, e, api: (contagem_ok(r, len(e["criticos"])), f"esperado {len(e['criticos'])} servidor(es)")),
    ("Quais servidores estão em estado de aviso?",
     {"get_overview", "list_servers"},
     lambda r, e, api: (all(s in r.lower() for s in e["avisos"]), f"esperado {e['avisos']}")),
    ("Qual é o uso de disco do srv-backup-01 agora?",
     {"get_server", "list_servers", "get_metrics"},
     lambda r, e, api: (any(abs(n - e["por_id"]["srv-backup-01"]["metrics"]["disk"]["value"]) <= 2 for n in numeros(r)),
                        f"esperado ~{e['por_id']['srv-backup-01']['metrics']['disk']['value']}%")),
    ("Existe algum alerta ativo no srv-web-01?",
     {"get_server", "list_alerts"},
     lambda r, e, api: ((sem_alertas_ok(r) if not e["por_id"]["srv-web-01"]["active_alerts"]["critical"]
                         + e["por_id"]["srv-web-01"]["active_alerts"]["warning"] else not sem_alertas_ok(r)),
                        f"esperado {e['por_id']['srv-web-01']['active_alerts']}")),
    ("Como está a temperatura do srv-app-02 nas últimas 6 horas?",
     {"get_metrics"},
     lambda r, e, api: (_temp_ok(r, api), "esperado mínimo/média/máximo próximos dos da API")),
    ("Quais são os limites de alerta de CPU que valem para o srv-db-01?",
     {"get_trigger_rules", "get_server"},
     lambda r, e, api: ("80" in r and "90" in r, "esperado aviso 80% e crítico 90%")),
]


def _temp_ok(resposta: str, api) -> bool:
    serie = api.get("servers/srv-app-02/metrics", params={"metric": "temp", "range": "6h"}).json()["items"][0]
    vals = [p["v"] for p in serie["points"] if p["v"] is not None]
    alvo = [min(vals), sum(vals) / len(vals), max(vals)]
    return any(abs(n - a) <= 2 for n in numeros(resposta) for a in alvo)


def perguntar(api, texto: str) -> tuple[dict, float]:
    t0 = time.perf_counter()
    r = api.post("assistant/messages", json={"message": texto}, timeout=300)
    return r.json() | {"_status": r.status_code}, time.perf_counter() - t0


def main() -> None:
    provedor = os.environ.get("SMI_LLM_PROVIDER", "ollama")
    with Ambiente(llm=provedor, simulador=True, historico="24h") as amb:
        status = amb.api.get("assistant/status").json()
        if not (status["available"] and status["mcp"]["connected"]):
            raise SystemExit(f"assistente indisponível: {status['detail']} / {status['mcp']['detail']}")
        modelo = f"{status['provider']} · {status['model']}"
        print(f"modelo: {modelo}; ferramentas MCP: {len(status['mcp']['tools'])}")
        time.sleep(15)
        print("aquecimento (carrega o modelo na memória)…")
        _, t_frio = perguntar(amb.api, "Olá")

        validos = {s["id"] for s in amb.api.get("servers").json()["items"]}
        registros = []
        for pergunta, ferramentas, verificar in PERGUNTAS:
            for i in range(REPETICOES):
                resp, seg = perguntar(amb.api, pergunta)
                if resp["_status"] != 200:
                    registros.append({"pergunta": pergunta, "erro": resp.get("error"), "segundos": round(seg, 1)})
                    print(f"  ERRO {resp.get('error')}")
                    continue
                texto = resp["reply"]
                usadas = {c["name"] for c in resp["tool_calls"]}
                ok, esperado = verificar(texto, estado(amb.api), amb.api)
                inventados = servidores_citados(texto) - validos
                registros.append({
                    "pergunta": pergunta, "repeticao": i + 1, "segundos": round(seg, 1),
                    "correta": bool(ok), "esperado": esperado,
                    "ferramenta_adequada": bool(usadas & ferramentas), "ferramentas": sorted(usadas),
                    "alucinou_servidor": sorted(inventados), "resposta": texto,
                })
                print(f"  [{'OK ' if ok else 'ERRO'}] {seg:5.1f} s  {pergunta[:55]:55}  ferramentas={sorted(usadas)}"
                      f"{'  INVENTOU ' + str(sorted(inventados)) if inventados else ''}", flush=True)

        print("relatório com análise da IA…")
        t0 = time.perf_counter()
        rep = amb.api.post("reports", json={"type": "incidents", "range": "24h"}).json()
        while (full := amb.api.get(f"reports/{rep['id']}").json())["status"] == "pending":
            time.sleep(1)
        t_relatorio = time.perf_counter() - t0

    validas = [r for r in registros if "erro" not in r]
    por_pergunta = {}
    for pergunta, _, _ in PERGUNTAS:
        rs = [r for r in validas if r["pergunta"] == pergunta]
        por_pergunta[pergunta] = {
            "acertos": sum(r["correta"] for r in rs), "total": len(rs),
            "ferramenta_adequada": sum(r["ferramenta_adequada"] for r in rs),
            "tempo_s": resumo([r["segundos"] for r in rs]),
        }
    acertos = sum(r["correta"] for r in validas)
    print(f"\nacertos: {acertos}/{len(validas)} ({acertos / len(validas) * 100:.0f}%), "
          f"ferramenta adequada {sum(r['ferramenta_adequada'] for r in validas)}/{len(validas)}, "
          f"respostas com servidor inventado: {sum(1 for r in validas if r['alucinou_servidor'])}")
    salvar("ia", {
        "modelo": modelo,
        "metodo": f"{len(PERGUNTAS)} perguntas com resposta conhecida, {REPETICOES} vezes cada em conversa nova; "
                  "conferência automática contra a API logo após cada resposta",
        "taxa_acerto_pct": round(acertos / len(validas) * 100, 1),
        "ferramenta_adequada_pct": round(sum(r["ferramenta_adequada"] for r in validas) / len(validas) * 100, 1),
        "respostas_com_servidor_inventado": sum(1 for r in validas if r["alucinou_servidor"]),
        "erros": len(registros) - len(validas),
        "tempo_resposta_s": resumo([r["segundos"] for r in validas]),
        "primeira_resposta_fria_s": round(t_frio, 1),
        "relatorio_com_ia": {"segundos": round(t_relatorio, 1), "gerado_por": full["generated_by"], "status": full["status"]},
        "por_pergunta": por_pergunta,
        "respostas": registros,
    })


if __name__ == "__main__":
    main()

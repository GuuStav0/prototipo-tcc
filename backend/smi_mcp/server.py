"""Servidor MCP do SMI (TCC 2.6).

Expõe a infraestrutura monitorada como ferramentas MCP. Ele não acessa os bancos: cada
ferramenta chama a API REST do SMI, então a IA enxerga exatamente o que o dashboard mostra.

Roda por stdio (padrão MCP para processos locais):
    python -m smi_mcp
O backend inicia este processo sozinho; também dá para conectá-lo a outros clientes MCP
(ex.: Claude Desktop), veja backend/README.md.

As respostas são resumidas de propósito: modelos locais têm janela de contexto pequena.
"""

import os
from datetime import datetime, timezone

import httpx
from mcp.server.mcpserver import MCPServer

API_URL = os.environ.get("SMI_API_URL", "http://127.0.0.1:8000/api/v1").rstrip("/")

mcp = MCPServer(
    "SMI - Monitoramento de Integridade",
    instructions=(
        "Ferramentas de consulta ao Sistema de Monitoramento de Integridade (SMI): servidores, "
        "métricas de hardware (CPU, memória, disco, temperatura), alertas e regras de gatilho."
    ),
)

_client: httpx.Client | None = None


def set_client(client: httpx.Client) -> None:
    """Permite trocar o cliente HTTP (usado nos testes)."""
    global _client
    _client = client


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(base_url=API_URL + "/", timeout=30)
    return _client


def _check(r: httpx.Response) -> dict:
    """Erros da API viram exceção com a mensagem do contrato; o MCP devolve isso à IA."""
    if r.status_code >= 400:
        try:
            msg = r.json()["error"]["message"]
        except Exception:
            msg = r.text[:200]
        raise ValueError(msg)
    return r.json()


def _get(path: str, **params) -> dict:
    # caminho relativo à base_url (".../api/v1"), sem a barra inicial
    params = {k: v for k, v in params.items() if v not in (None, "")}
    return _check(_http().get(path.lstrip("/"), params=params))


def _post(path: str, body: dict) -> dict:
    return _check(_http().post(path.lstrip("/"), json=body))


# ---------------------------------------------------------------- formatação
UNITS = {"percent": "%", "celsius": "°C", "bool": ""}


def _ago(iso: str | None) -> str | None:
    if not iso:
        return None
    s = int((datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds())
    if s < 60:
        return f"há {s} s"
    if s < 3600:
        return f"há {s // 60} min"
    if s < 86400:
        return f"há {s // 3600} h"
    return f"há {s // 86400} d"


def _dur(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    s = int(seconds)
    if s < 3600:
        return f"{s // 60} min {s % 60} s"
    return f"{s // 3600} h {s % 3600 // 60} min"


def _val(reading: dict) -> str | None:
    v = reading.get("value")
    if v is None:
        return None
    if reading.get("unit") == "bool":
        return "online" if v >= 1 else "offline"
    return f"{round(v, 1)}{UNITS.get(reading.get('unit'), '')}"


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _local(iso: str | None) -> str | None:
    """Horário local do servidor do SMI (o modelo não precisa converter fuso)."""
    return _parse(iso).astimezone().strftime("%d/%m %H:%M") if iso else None


def _alert(a: dict) -> dict:
    unit = UNITS.get(a["unit"], "")
    active = a["status"] == "active"
    end = _parse(a["resolved_at"]) if a["resolved_at"] else datetime.now(timezone.utc)
    item = {
        "id": a["id"],
        "host": a["host_id"],
        "gatilho": a["trigger_name"],
        "metrica": a["metric"],
        "status": "ativo" if active else "resolvido",
        "severidade_atual" if active else "pior_severidade": a["severity"] if active else a["peak_severity"],
        "pior_valor": f"{round(a['value_peak'], 1)}{unit}",
        "limiar": f"{a['threshold']}{unit}",
        "inicio": _local(a["started_at"]),
        "duracao": _dur((end - _parse(a["started_at"])).total_seconds()),
    }
    if active:  # num alerta resolvido o valor final já está normal e só confunde
        item["valor_atual"] = f"{round(a['value_last'], 1)}{unit}"
        item["reconhecido_pela_equipe"] = bool(a["acknowledged_at"])
    else:
        item["fim"] = _local(a["resolved_at"])
    return item


def _rule(r: dict) -> dict:
    return {
        "id": r["id"],
        "nome": r["name"],
        "metrica": r["metric"],
        "escopo": r["host_id"] or "global",
        "operador": r["operator"],
        "aviso": r["warning_threshold"],
        "critico": r["critical_threshold"],
        "duracao_s": r["duration_seconds"],
        "ativa": r["enabled"],
    }


# ---------------------------------------------------------------- ferramentas
SEVERITY_ORDER = {"critical": 0, "warning": 1, "unknown": 2, "ok": 3}


@mcp.tool()
def get_overview(range: str = "24h") -> dict:
    """Resumo geral da infraestrutura: disponibilidade, quantos servidores em cada estado e a
    lista dos servidores com problema (do mais grave para o menos grave) com seus alertas
    ativos. Use primeiro para perguntas gerais e para saber qual servidor está pior.

    range: janela usada na disponibilidade e no MTTR (1h, 6h, 24h, 7d ou 30d).
    """
    o = _get("/overview", range=range)
    servers = _get("/servers")["items"]
    active = _get("/alerts", status="active", limit=200)["items"]

    problems = []
    for s in servers:
        if s["status"] == "ok":
            continue
        alerts = [a for a in active if a["host_id"] == s["id"]]
        problems.append({
            "servidor": s["id"],
            "estado": s["status"],
            "alertas_criticos": s["active_alerts"]["critical"],
            "alertas_aviso": s["active_alerts"]["warning"],
            "alertas_ativos": [
                f"{a['trigger_name']} ({a['severity']}): {round(a['value_last'], 1)}{UNITS.get(a['unit'], '')}, "
                f"limiar {a['threshold']}{UNITS.get(a['unit'], '')}, desde {_ago(a['started_at'])}"
                for a in sorted(active, key=lambda a: SEVERITY_ORDER[a["severity"]]) if a["host_id"] == s["id"]
            ] if alerts else [],
        })
    problems.sort(key=lambda p: (SEVERITY_ORDER[p["estado"]], -p["alertas_criticos"], -p["alertas_aviso"]))

    return {
        "janela": o["range"],
        "disponibilidade_percent": o["availability"]["percent"],
        "meta_slo_percent": o["availability"]["slo_percent"],
        "servidores_por_estado": o["hosts"],
        "total_alertas_ativos": o["alerts_active"],
        "mttr": _dur(o["mttr_seconds"]),
        "servidores_com_problema_do_pior_para_o_melhor": problems,
    }


@mcp.tool()
def list_servers(status: str | None = None) -> list[dict]:
    """Lista os servidores monitorados (do pior estado para o melhor) com o último valor de
    CPU, memória, disco e temperatura.

    status: filtra por estado (ok, warning, critical ou unknown). Vazio = todos.
    """
    items = sorted(_get("/servers", status=status)["items"],
                   key=lambda s: (SEVERITY_ORDER[s["status"]], -s["active_alerts"]["critical"], s["id"]))
    return [
        {
            "id": s["id"],
            "funcao": s["role"],
            "estado": s["status"],
            "cpu": _val(s["metrics"]["cpu"]),
            "memoria": _val(s["metrics"]["ram"]),
            "disco": _val(s["metrics"]["disk"]),
            "temperatura": _val(s["metrics"]["temp"]),
            "alcance": _val(s["metrics"]["reachable"]),
            "alertas_ativos": s["active_alerts"],
            "ultima_coleta": _ago(s["last_seen_at"]),
        }
        for s in items
    ]


@mcp.tool()
def get_server(host_id: str) -> dict:
    """Detalhes de um servidor: dados de cadastro, valores atuais com o estado de cada métrica,
    alertas ativos e as regras de gatilho que valem para ele.

    host_id: identificador do servidor, ex. srv-app-02.
    """
    s = _get(f"/servers/{host_id}")
    alerts = _get("/alerts", host_id=host_id, status="active", limit=20)["items"]
    rules = [r for r in _get("/triggers", host_id=host_id)["items"] if r["enabled"]]
    return {
        "id": s["id"],
        "funcao": s["role"],
        "sistema": s["os"],
        "endereco": s["address"],
        "estado": s["status"],
        "uptime_horas": round(s["uptime_seconds"] / 3600, 1) if s["uptime_seconds"] else None,
        "ultima_coleta": _ago(s["last_seen_at"]),
        "metricas": {m: {"valor": _val(r), "estado": r["status"]} for m, r in s["metrics"].items()},
        "alertas_ativos": [_alert(a) for a in alerts],
        "regras": [_rule(r) for r in rules],
    }


@mcp.tool()
def get_metrics(host_id: str, metric: str, range: str = "24h") -> dict:
    """Histórico de uma métrica de um servidor, com estatísticas (mínimo, média, máximo, último),
    tendência e até 24 pontos amostrados. Use para analisar evolução e picos.

    host_id: ex. srv-db-01. metric: cpu, ram, disk, temp ou reachable.
    range: 1h, 6h, 24h, 7d ou 30d.
    """
    series = _get(f"/servers/{host_id}/metrics", metric=metric, range=range)["items"][0]
    unit = UNITS.get(series["unit"], "")
    values = [p["v"] for p in series["points"] if p["v"] is not None]
    if not values:
        return {"host": host_id, "metrica": metric, "janela": range, "aviso": "sem dados no período"}

    # tendência: média do último quarto comparada à do primeiro quarto
    q = max(1, len(values) // 4)
    first, last = sum(values[:q]) / q, sum(values[-q:]) / q
    delta = last - first
    trend = "estável" if abs(delta) < 3 else ("subindo" if delta > 0 else "caindo")

    # só pontos com valor, no horário local (janela vazia na agregação não é falha de coleta)
    com_valor = [p for p in series["points"] if p["v"] is not None]
    stride = max(1, len(com_valor) // 24)
    curto = range in ("1h", "6h", "24h")
    sample = [[_parse(p["t"]).astimezone().strftime("%H:%M" if curto else "%d/%m %H:%M"), round(p["v"], 1)]
              for p in com_valor[::stride]]

    # lacuna de coleta de verdade = mais de 10 min seguidos sem nenhuma leitura
    lacunas, inicio_vazio = [], None
    for p in series["points"]:
        if p["v"] is None and inicio_vazio is None:
            inicio_vazio = p["t"]
        elif p["v"] is not None and inicio_vazio is not None:
            if (_parse(p["t"]) - _parse(inicio_vazio)).total_seconds() > 600:
                lacunas.append(f"{_local(inicio_vazio)} a {_local(p['t'])}")
            inicio_vazio = None
    return {
        "host": host_id,
        "metrica": metric,
        "unidade": unit,
        "janela": range,
        "minimo": round(min(values), 1),
        "media": round(sum(values) / len(values), 1),
        "maximo": round(max(values), 1),
        "ultimo": round(values[-1], 1),
        "tendencia": f"{trend} ({delta:+.1f}{unit} entre o início e o fim da janela)",
        "lacunas_de_coleta": lacunas or "nenhuma (a coleta não ficou mais de 10 min sem dados)",
        "amostras_hora_valor": sample,
    }


@mcp.tool()
def list_alerts(status: str | None = None, host_id: str | None = None,
                severity: str | None = None, hours: int | None = None, limit: int = 20) -> dict:
    """Histórico de alertas (disparos de gatilho), mais recentes primeiro. Use para responder
    o que aconteceu, correlacionar eventos e calcular durações.

    status: active ou resolved (vazio = ambos). host_id: filtra um servidor.
    severity: warning ou critical. hours: só alertas ativos nas últimas N horas.
    limit: máximo de itens (até 50).
    """
    since = None
    if hours:
        since = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() - hours * 3600, timezone.utc).isoformat()
    data = _get("/alerts", status=status, host_id=host_id, severity=severity,
                **{"from": since}, limit=min(limit, 50))
    return {"total": data["total"], "alertas": [_alert(a) for a in data["items"]]}


@mcp.tool()
def get_trigger_rules(host_id: str | None = None) -> list[dict]:
    """Regras do motor de gatilhos (limiares de aviso e crítico e a duração exigida).

    host_id: mostra as regras que valem para esse servidor (globais + específicas). Vazio = todas.
    """
    return [_rule(r) for r in _get("/triggers", host_id=host_id)["items"]]


@mcp.tool()
def create_report(type: str, range: str = "7d") -> dict:
    """Pede a geração de um relatório. Ele é gerado em segundo plano e aparece na aba Relatórios.

    type: availability (disponibilidade), incidents (incidentes), performance (desempenho)
    ou audit (auditoria de configuração). range: 24h, 7d ou 30d.
    """
    r = _post("/reports", {"type": type, "range": range, "requested_by": "Assistente IA"})
    return {"id": r["id"], "titulo": r["title"], "status": r["status"],
            "mensagem": "Relatório em geração; ficará disponível na aba Relatórios em instantes."}


def main() -> None:
    mcp.run()  # stdio


if __name__ == "__main__":
    main()

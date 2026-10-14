"""Assistente de IA: laço de ferramentas, rotas, servidor MCP e análise dos relatórios.
Nenhum teste chama um modelo de verdade: o LLM é simulado (FakeProvider)."""

import asyncio
import json
import sys
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.assistant import get_assistant
from app.assistant.agent import MAX_STEPS, Assistant
from app.assistant.providers import LLMUnavailable, ToolCall, ToolSpec, Turn
from app.assistant.toolbox import MCPToolbox
from app.main import app
from app.reports import _insert_analysis, generate_report
from conftest import send

API = "/api/v1"


class FakeProvider:
    """LLM roteirizado: devolve os Turns da lista, na ordem, e registra o que recebeu."""

    name, model = "fake", "fake-1"

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def user(self, text):
        return {"role": "user", "content": text}

    def tool_results(self, results):
        return [{"role": "tool", "name": c.name, "content": t, "error": e} for c, t, e in results]

    async def complete(self, system, messages, tools):
        self.calls.append({"messages": list(messages), "tools": [t.name for t in tools]})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    async def status(self):
        return True, "ok"


class FakeToolbox:
    def __init__(self, results=None):
        self.results = results or {}
        self.called = []

    async def tools(self):
        return [ToolSpec("list_servers", "lista", {"type": "object"}),
                ToolSpec("get_server", "detalhe", {"type": "object"})]

    async def call(self, name, arguments):
        self.called.append((name, arguments))
        result = self.results.get(name, "{}")
        if isinstance(result, Exception):
            raise result
        return result, False

    async def status(self):
        return True, ["list_servers", "get_server"], ""


def turn(text="", calls=()):
    return Turn(text=text, tool_calls=list(calls), native={"role": "assistant", "content": text})


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- laço do agente
def test_answers_without_tools():
    a = Assistant(FakeProvider([turn("Olá!")]), FakeToolbox())
    cid, reply, used = run(a.chat(None, "oi"))
    assert reply == "Olá!" and used == [] and cid


def test_runs_tools_then_answers():
    provider = FakeProvider([
        turn(calls=[ToolCall("1", "get_server", {"host_id": "srv-app-02"})]),
        turn("O srv-app-02 está crítico."),
    ])
    toolbox = FakeToolbox({"get_server": '{"estado": "critical"}'})
    cid, reply, used = run(Assistant(provider, toolbox).chat(None, "como está o srv-app-02?"))
    assert reply == "O srv-app-02 está crítico."
    assert used == [{"name": "get_server", "arguments": {"host_id": "srv-app-02"}}]
    assert toolbox.called == [("get_server", {"host_id": "srv-app-02"})]
    # o resultado da ferramenta chegou ao modelo na segunda chamada
    assert provider.calls[1]["messages"][-1]["content"] == '{"estado": "critical"}'
    assert provider.calls[0]["tools"] == ["list_servers", "get_server"]


def test_tool_error_goes_back_to_model():
    provider = FakeProvider([turn(calls=[ToolCall("1", "get_server", {"host_id": "x"})]), turn("Não existe.")])
    toolbox = FakeToolbox({"get_server": ValueError("servidor 'x' não encontrado")})
    _, reply, _ = run(Assistant(provider, toolbox).chat(None, "x?"))
    last = provider.calls[1]["messages"][-1]
    assert last["error"] is True and "não encontrado" in last["content"] and reply == "Não existe."


def test_stops_after_max_steps():
    loop_forever = [turn(calls=[ToolCall(str(i), "list_servers", {})]) for i in range(MAX_STEPS)]
    _, reply, used = run(Assistant(FakeProvider(loop_forever), FakeToolbox()).chat(None, "?"))
    assert len(used) == MAX_STEPS and "limite" in reply


def test_conversation_keeps_history_and_rolls_back_on_failure():
    provider = FakeProvider([turn("Primeira."), LLMUnavailable("Ollama fora"), turn("Terceira.")])
    a = Assistant(provider, FakeToolbox())
    cid, _, _ = run(a.chat(None, "um"))
    with pytest.raises(LLMUnavailable):
        run(a.chat(cid, "dois"))
    run(a.chat(cid, "três"))
    # a pergunta que falhou não ficou no histórico
    texts = [m["content"] for m in provider.calls[-1]["messages"]]
    assert any(t.endswith("um") for t in texts) and not any(t.endswith("dois") for t in texts)
    assert texts[-1].endswith("três") and "Horário local" in texts[-1]


# ---------------------------------------------------------------- rotas
@pytest.fixture
def with_assistant(client):
    holder = {}

    def use(provider, toolbox=None):
        holder["a"] = Assistant(provider, toolbox or FakeToolbox())
        app.dependency_overrides[get_assistant] = lambda: holder["a"]
        return holder["a"]

    yield use
    app.dependency_overrides.pop(get_assistant, None)


def test_chat_route(client, with_assistant):
    with_assistant(FakeProvider([turn(calls=[ToolCall("1", "list_servers", {})]), turn("**10** servidores.")]))
    r = client.post(f"{API}/assistant/messages", json={"message": "quantos servidores?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"] == "**10** servidores." and body["conversation_id"]
    assert body["tool_calls"] == [{"name": "list_servers", "arguments": {}}]


def test_chat_route_errors(client, with_assistant):
    with_assistant(FakeProvider([LLMUnavailable("O Ollama não está rodando.")]))
    r = client.post(f"{API}/assistant/messages", json={"message": "oi"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "assistant_unavailable"
    assert client.post(f"{API}/assistant/messages", json={"message": ""}).status_code == 422


def test_assistant_disabled(client):
    r = client.post(f"{API}/assistant/messages", json={"message": "oi"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "assistant_disabled"
    s = client.get(f"{API}/assistant/status").json()
    assert s["enabled"] is False and s["available"] is False


def test_status_route(client, with_assistant):
    with_assistant(FakeProvider([]))
    s = client.get(f"{API}/assistant/status").json()
    assert s == {"enabled": True, "provider": "fake", "model": "fake-1", "available": True, "detail": "ok",
                 "mcp": {"connected": True, "tools": ["list_servers", "get_server"], "detail": ""}}


# ---------------------------------------------------------------- ferramentas do servidor MCP
@pytest.fixture
def mcp_tools(client):
    """As funções das ferramentas, consultando a API de teste."""
    from smi_mcp import server

    server.set_client(TestClient(app, base_url="http://testserver/api/v1/"))
    yield server
    server.set_client(None)


def test_mcp_tools_return_compact_data(client, mcp_tools, t0):
    now = datetime.now(timezone.utc)
    send(client, [("srv-app-02", "cpu", 97, now), ("srv-app-02", "reachable", 1, now)])
    from conftest import series
    series(client, "srv-web-01", "cpu", [95] * 6, t0)

    servers = mcp_tools.list_servers()
    app02 = next(s for s in servers if s["id"] == "srv-app-02")
    assert app02["cpu"] == "97.0%" and app02["alcance"] == "online"
    assert [s["id"] for s in mcp_tools.list_servers(status="critical")] == ["srv-web-01"]
    assert servers[0]["id"] == "srv-web-01"  # o pior primeiro

    detail = mcp_tools.get_server("srv-web-01")
    assert detail["estado"] == "critical" and len(detail["regras"]) == 5
    assert detail["alertas_ativos"][0]["gatilho"] == "CPU elevada"

    overview = mcp_tools.get_overview()
    assert overview["total_alertas_ativos"] == {"warning": 0, "critical": 1}
    worst = overview["servidores_com_problema_do_pior_para_o_melhor"][0]
    assert worst["servidor"] == "srv-web-01" and worst["estado"] == "critical"
    assert worst["alertas_ativos"][0].startswith("CPU elevada (critical): 95")

    metrics = mcp_tools.get_metrics("srv-web-01", "cpu", "1h")
    assert metrics["maximo"] == 95 and metrics["unidade"] == "%"
    assert len(metrics["amostras_hora_valor"]) <= 25

    alerts = mcp_tools.list_alerts(status="active")
    assert alerts["total"] == 1 and alerts["alertas"][0]["host"] == "srv-web-01"
    assert len(mcp_tools.get_trigger_rules()) == 5


def test_mcp_tool_errors_use_api_message(client, mcp_tools):
    with pytest.raises(ValueError, match="não encontrado"):
        mcp_tools.get_server("nao-existe")
    report = mcp_tools.create_report("incidents", "24h")
    assert report["status"] == "pending"


def test_mcp_server_over_stdio():
    """Sobe o servidor MCP de verdade (processo separado, protocolo MCP por stdio).
    A API aponta para uma porta fechada: listar ferramentas funciona, chamar devolve erro."""
    async def scenario():
        toolbox = MCPToolbox("http://127.0.0.1:9/api/v1")
        try:
            names = [t.name for t in await toolbox.tools()]
            text, is_error = await toolbox.call("get_overview", {})
        finally:
            await toolbox.close()
        return names, text, is_error

    names, text, is_error = asyncio.run(scenario())
    assert set(names) == {"get_overview", "list_servers", "get_server", "get_metrics",
                          "list_alerts", "get_trigger_rules", "create_report"}
    assert is_error is True


# ---------------------------------------------------------------- relatórios com análise da IA
def test_report_gets_ai_analysis(client, t0):
    from app.database import SessionLocal
    from app.metrics_store import get_metrics_store
    from app.models import Report

    r = client.post(f"{API}/reports", json={"type": "incidents", "range": "24h"}).json()
    seen = {}

    def fake_analyze(content):
        seen["content"] = content
        return "**Resumo executivo**: nada crítico."

    generate_report(r["id"], get_metrics_store(), analyze=fake_analyze)
    with SessionLocal() as db:
        rep = db.get(Report, r["id"])
        assert rep.generated_by == "assistant"
        assert "## Análise do assistente (IA)" in rep.content and "nada crítico" in rep.content
        # a análise fica entre o Resumo e as tabelas
        assert rep.content.index("## Resumo") < rep.content.index("## Análise") < rep.content.index("## Alertas")
    assert "## Resumo" in seen["content"]  # a IA recebeu os dados calculados


def test_report_survives_ai_failure(client):
    from app.database import SessionLocal
    from app.metrics_store import get_metrics_store
    from app.models import Report

    r = client.post(f"{API}/reports", json={"type": "availability", "range": "24h"}).json()

    def broken(_):
        raise RuntimeError("Ollama fora do ar")

    generate_report(r["id"], get_metrics_store(), analyze=broken)
    with SessionLocal() as db:
        rep = db.get(Report, r["id"])
        assert rep.status == "ready" and rep.generated_by == "system"
        assert "Análise por IA indisponível: Ollama fora do ar" in rep.content


def test_insert_analysis_position():
    content = "# T\n\n## Resumo\n\n- a\n\n## Alertas\n\nx\n"
    out = _insert_analysis(content, "análise")
    assert out.index("## Resumo") < out.index("análise") < out.index("## Alertas")
    assert _insert_analysis("# sem seções\n", "z").endswith("z\n")

import time
from datetime import datetime, timedelta, timezone

from conftest import TOKEN, alerts, send, series

API = "/api/v1"


# ---------------------------------------------------------------- ingestão
def test_ingest_requires_token(client):
    r = client.post(f"{API}/ingest/metrics", json={"source": "simulator", "samples": []})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_token"


def test_ingest_rejects_invalid_samples_individually(client):
    now = datetime.now(timezone.utc)
    result = send(client, [
        ("srv-web-01", "cpu", 50, now),                       # ok
        ("srv-nao-existe", "cpu", 50, now),                    # host desconhecido
        ("srv-web-01", "cpu", 150, now),                       # fora da faixa
        ("srv-web-01", "fan", 1, now),                         # métrica desconhecida
        ("srv-web-01", "reachable", 0.5, now),                 # reachable não binário
        ("srv-web-01", "cpu", 50, now + timedelta(hours=1)),   # no futuro
        ("srv-web-01", "uptime", 3600, now),                   # ok
    ])
    assert result["accepted"] == 2
    assert [r["index"] for r in result["rejected"]] == [1, 2, 3, 4, 5]
    assert client.get(f"{API}/servers/srv-web-01").json()["uptime_seconds"] == 3600


# ---------------------------------------------------------------- servidores
def test_server_crud_and_credentials_never_returned(client):
    body = {"id": "srv-novo-01", "name": "srv-novo-01", "address": "10.0.9.9", "role": "Teste",
            "snmp": {"version": "v3", "username": "monitor", "auth_password": "segredo"}}
    r = client.post(f"{API}/servers", json=body)
    assert r.status_code == 201, r.text
    assert "segredo" not in r.text and "monitor" not in r.text
    assert r.json()["collection"]["snmp"]["version"] == "v3"
    assert r.json()["status"] == "unknown"  # ainda sem leituras

    assert client.post(f"{API}/servers", json=body).status_code == 409

    r = client.patch(f"{API}/servers/srv-novo-01", json={"location": "Rack B1"})
    assert r.json()["location"] == "Rack B1" and r.json()["role"] == "Teste"
    r = client.patch(f"{API}/servers/srv-novo-01", json={"location": None})
    assert r.json()["location"] is None
    assert client.patch(f"{API}/servers/srv-novo-01", json={"name": None}).status_code == 422

    assert client.delete(f"{API}/servers/srv-novo-01").status_code == 204
    r = client.get(f"{API}/servers/srv-novo-01")
    assert r.status_code == 404 and r.json()["error"]["code"] == "server_not_found"


def test_invalid_server_id_uses_error_format(client):
    r = client.post(f"{API}/servers", json={"id": "Com Espaço", "name": "x", "address": "y"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_host_status_ok_unknown_and_metric_snapshot(client):
    now = datetime.now(timezone.utc)
    send(client, [("srv-web-01", "cpu", 42.5, now), ("srv-web-01", "reachable", 1, now),
                  ("srv-web-02", "cpu", 30, now - timedelta(minutes=5))])  # leitura velha
    by_id = {s["id"]: s for s in client.get(f"{API}/servers").json()["items"]}
    web1, web2 = by_id["srv-web-01"], by_id["srv-web-02"]
    assert web1["status"] == "ok"
    assert web1["metrics"]["cpu"] == {**web1["metrics"]["cpu"], "value": 42.5, "unit": "percent",
                                      "status": "ok", "source": "simulator"}
    assert web1["metrics"]["temp"]["value"] is None and web1["metrics"]["temp"]["status"] == "unknown"
    assert web2["status"] == "unknown"
    assert by_id["srv-db-01"]["status"] == "unknown"  # nunca coletado

    ok_only = client.get(f"{API}/servers", params={"status": "ok"}).json()["items"]
    assert [s["id"] for s in ok_only] == ["srv-web-01"]


def test_metric_status_follows_active_alert(client, t0):
    series(client, "srv-web-01", "cpu", [95] * 6, t0)
    host = client.get(f"{API}/servers/srv-web-01").json()
    assert host["metrics"]["cpu"]["status"] == "critical"
    assert host["status"] == "critical"  # alerta ativo vale mesmo com leitura antiga


# ---------------------------------------------------------------- séries
def test_series_are_bucketed_with_gaps(client):
    start = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    # leituras em 12:00, 12:01 e 12:03 (12:02 sem dados)
    send(client, [("srv-web-01", "cpu", v, start + timedelta(minutes=m))
                  for v, m in ((10, 0), (20, 1), (40, 3))])
    r = client.get(f"{API}/servers/srv-web-01/metrics", params={
        "metric": "cpu,temp", "from": start.isoformat(), "to": (start + timedelta(minutes=4)).isoformat(),
        "step": 60})
    assert r.status_code == 200, r.text
    cpu, temp = r.json()["items"]
    assert cpu["unit"] == "percent" and cpu["step_seconds"] == 60 and "from" in cpu
    assert [p["v"] for p in cpu["points"]] == [10, 20, None, 40]
    assert cpu["points"][0]["t"].startswith("2026-10-01T12:00:00")
    assert all(p["v"] is None for p in temp["points"])

    r = client.get(f"{API}/servers/srv-web-01/metrics", params={
        "metric": "cpu", "from": start.isoformat(), "to": (start + timedelta(minutes=4)).isoformat(),
        "step": 120, "aggregation": "max"})
    assert [p["v"] for p in r.json()["items"][0]["points"]] == [20, 40]


def test_series_validation(client):
    url = f"{API}/servers/srv-web-01/metrics"
    assert client.get(url, params={"metric": "fan"}).json()["error"]["code"] == "invalid_metric"
    assert client.get(url, params={"metric": "cpu", "range": "2h"}).status_code == 422
    assert client.get(f"{API}/servers/nao-existe/metrics", params={"metric": "cpu"}).status_code == 404
    r = client.get(url, params={"metric": "cpu", "range": "24h"})
    # 24 h / 300 pontos = 288 s -> arredonda para 300 s; +1 janela pelo alinhamento à época
    assert r.json()["items"][0]["step_seconds"] == 300
    assert len(r.json()["items"][0]["points"]) in (288, 289)
    r = client.get(url, params={"metric": "cpu", "range": "7d"})
    assert r.json()["items"][0]["step_seconds"] == 3600


# ---------------------------------------------------------------- gatilhos
def test_trigger_threshold_validation(client):
    bad = {"name": "x", "metric": "cpu", "operator": "gt",
           "warning_threshold": 90, "critical_threshold": 80}
    r = client.post(f"{API}/triggers", json=bad)
    assert r.status_code == 422 and "critical_threshold" in r.json()["error"]["message"]

    rule = client.get(f"{API}/triggers", params={"metric": "cpu"}).json()["items"][0]
    r = client.patch(f"{API}/triggers/{rule['id']}", json={"critical_threshold": 70})
    assert r.status_code == 422
    r = client.patch(f"{API}/triggers/{rule['id']}", json={"warning_threshold": None})
    assert r.status_code == 200 and r.json()["warning_threshold"] is None

    r = client.post(f"{API}/triggers", json={**bad, "warning_threshold": 50, "host_id": "nao-existe"})
    assert r.json()["error"]["code"] == "server_not_found"


def test_deleting_trigger_keeps_alert_history(client, t0):
    series(client, "srv-web-01", "cpu", [95] * 6, t0)
    [a] = alerts(client)
    assert client.delete(f"{API}/triggers/{a['trigger_id']}").status_code == 204
    [a] = alerts(client)
    assert a["status"] == "resolved" and a["trigger_name"] == "CPU elevada"


# ---------------------------------------------------------------- alertas
def test_alert_acknowledge_and_validation(client, t0):
    series(client, "srv-web-01", "cpu", [95] * 6, t0)
    [a] = alerts(client)
    r = client.patch(f"{API}/alerts/{a['id']}", json={
        "acknowledged": True, "acknowledged_by": "Paulo", "validation": "true_positive", "note": "ok"})
    body = r.json()
    assert body["acknowledged_at"] and body["acknowledged_by"] == "Paulo"
    assert body["validation"] == "true_positive"
    r = client.patch(f"{API}/alerts/{a['id']}", json={"acknowledged": False})
    assert r.json()["acknowledged_at"] is None and r.json()["validation"] == "true_positive"


def test_alert_filters_and_pagination(client, t0):
    series(client, "srv-web-01", "cpu", [95] * 6, t0)
    series(client, "srv-web-02", "ram", [85] * 6, t0)
    assert len(alerts(client, severity="critical")) == 1
    assert len(alerts(client, host_id="srv-web-02")) == 1
    r = client.get(f"{API}/alerts", params={"limit": 1}).json()
    assert r["total"] == 2 and len(r["items"]) == 1


# ---------------------------------------------------------------- visão geral e saúde
def test_overview(client, t0):
    now = datetime.now(timezone.utc)
    series(client, "srv-web-01", "cpu", [95] * 6, t0)                    # crítico ativo
    series(client, "srv-web-02", "cpu", [85] * 5 + [40] * 5, t0)          # resolvido
    send(client, [("srv-db-01", "reachable", v, now - timedelta(seconds=s))
                  for v, s in ((1, 30), (1, 20), (1, 10), (0, 5))])
    o = client.get(f"{API}/overview").json()
    assert o["hosts"]["total"] == 10
    assert o["hosts"]["critical"] == 1 and o["hosts"]["ok"] == 1  # srv-db-01 tem dados recentes
    assert o["alerts_active"] == {"warning": 0, "critical": 1}
    assert o["availability"] == {"percent": 75.0, "slo_percent": 99.9}
    assert o["mttr_seconds"] == 60 + 15  # do disparo (t0+60) à resolução (t0+135)
    assert len(o["recent_alerts"]) == 2


def test_health(client):
    h = client.get(f"{API}/health").json()
    assert h["status"] == "ok"
    assert h["components"] == {"database": "ok", "influxdb": "disabled", "last_ingest_at": None}


# ---------------------------------------------------------------- relatórios
def _wait_ready(client, report_id):
    for _ in range(50):
        r = client.get(f"{API}/reports/{report_id}").json()
        if r["status"] != "pending":
            return r
        time.sleep(0.05)
    raise AssertionError("relatório não ficou pronto")


def test_reports_are_generated_in_background(client, t0):
    series(client, "srv-web-01", "cpu", [95] * 6, t0)
    for rtype in ("availability", "incidents", "performance", "audit"):
        r = client.post(f"{API}/reports", json={"type": rtype, "range": "24h"})
        assert r.status_code == 202 and r.json()["status"] == "pending"
        report = _wait_ready(client, r.json()["id"])
        assert report["status"] == "ready", report["summary"]
        assert report["content"].startswith("# ")
    incidents = client.get(f"{API}/reports").json()["items"]
    assert len(incidents) == 4 and all(r["content"] is None for r in incidents)


def test_report_validation(client):
    r = client.post(f"{API}/reports", json={"type": "incidents", "host_ids": ["nao-existe"]})
    assert r.status_code == 422
    r = client.post(f"{API}/reports", json={"type": "incidents", "period_from": "2026-10-01T00:00:00Z"})
    assert r.status_code == 422


def test_assistant_not_implemented_yet(client):
    r = client.post(f"{API}/assistant/messages", json={"message": "oi"})
    assert r.status_code == 501 and r.json()["error"]["code"] == "not_implemented"

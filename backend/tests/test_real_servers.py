"""Etapa 5: servidores reais x simulados, watchdog de ausência de dados e migração do banco."""

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from app.migrations import upgrade
from app.watchdog import check_once
from conftest import TOKEN, alerts

API = "/api/v1"


def post(client, source, samples):
    r = client.post(f"{API}/ingest/metrics", headers=TOKEN, json={
        "source": source,
        "samples": [{"host_id": h, "metric": m, "value": v, "collected_at": at.isoformat()}
                    for h, m, v, at in samples],
    })
    assert r.status_code == 202, r.text
    return r.json()


def create_real(client, host_id="vps-01", agent=True, snmp=False):
    r = client.post(f"{API}/servers", json={
        "id": host_id, "name": host_id, "address": "100.64.0.2", "role": "VPS",
        "agent": {"enabled": agent}, "snmp": {"enabled": snmp},
    })
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- modo simulado x real
def test_new_servers_are_real_and_seed_is_simulated(client):
    assert create_real(client)["mode"] == "real"
    modes = {s["id"]: s["mode"] for s in client.get(f"{API}/servers").json()["items"]}
    assert modes["srv-web-01"] == "simulated" and modes["vps-01"] == "real"
    real = client.get(f"{API}/servers", params={"mode": "real"}).json()["items"]
    assert [s["id"] for s in real] == ["vps-01"]


def test_sources_do_not_mix(client):
    create_real(client, agent=True, snmp=False)
    now = datetime.now(timezone.utc)
    # simulador não escreve em servidor real
    r = post(client, "simulator", [("vps-01", "cpu", 50, now)])
    assert r["accepted"] == 0 and "é real" in r["rejected"][0]["reason"]
    # agente não escreve em servidor simulado
    r = post(client, "agent", [("srv-web-01", "cpu", 50, now)])
    assert r["accepted"] == 0 and "é simulado" in r["rejected"][0]["reason"]
    # SNMP desativado no cadastro do vps-01
    r = post(client, "snmp", [("vps-01", "cpu", 50, now)])
    assert r["accepted"] == 0 and "desativada" in r["rejected"][0]["reason"]
    # combinação certa
    assert post(client, "agent", [("vps-01", "cpu", 50, now)])["accepted"] == 1
    # fonte interna não pode ser enviada de fora
    r = client.post(f"{API}/ingest/metrics", headers=TOKEN, json={"source": "watchdog", "samples": []})
    assert r.status_code == 422


def test_switching_mode(client):
    create_real(client)
    r = client.patch(f"{API}/servers/vps-01", json={"mode": "simulated"})
    assert r.json()["mode"] == "simulated"
    now = datetime.now(timezone.utc)
    assert post(client, "simulator", [("vps-01", "cpu", 10, now)])["accepted"] == 1
    assert client.patch(f"{API}/servers/vps-01", json={"mode": None}).status_code == 422
    assert client.patch(f"{API}/servers/vps-01", json={"mode": "outro"}).status_code == 422


# ---------------------------------------------------------------- watchdog
def test_watchdog_flags_silent_real_server(client):
    create_real(client)
    start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=10)
    # o agente enviou até start+60 s e depois sumiu
    post(client, "agent", [("vps-01", m, v, start + timedelta(seconds=s))
                           for s in (0, 15, 30, 45, 60) for m, v in (("cpu", 20), ("reachable", 1))])

    assert check_once(start, now=start + timedelta(seconds=75)) == []        # 15 s de silêncio: ok
    assert check_once(start, now=start + timedelta(seconds=90)) == ["vps-01"]  # 30 s: marca
    for s in (105, 120, 135):
        check_once(start, now=start + timedelta(seconds=s))
    [a] = alerts(client, host_id="vps-01")
    assert a["trigger_name"] == "Host inalcançável" and a["severity"] == "critical"

    host = client.get(f"{API}/servers/vps-01").json()
    assert host["status"] == "critical"
    assert host["metrics"]["reachable"]["source"] == "watchdog"
    # "última coleta" continua sendo a última leitura real do agente
    assert host["last_seen_at"].startswith((start + timedelta(seconds=60)).isoformat()[:19])
    # simulados nunca são marcados pelo watchdog
    assert all(a["host_id"] == "vps-01" for a in alerts(client))


def test_watchdog_ignores_downtime_of_the_monitoring_itself(client):
    """PC do monitoramento desligado durante horas: ao religar, o servidor ganha um prazo
    antes de ser considerado fora do ar (não gera alerta falso)."""
    create_real(client)
    long_ago = datetime.now(timezone.utc) - timedelta(hours=5)
    post(client, "agent", [("vps-01", "reachable", 1, long_ago)])
    api_started = datetime.now(timezone.utc)
    assert check_once(api_started, now=api_started + timedelta(seconds=15)) == []
    # o agente reenviou (buffer) e voltou a enviar ao vivo
    post(client, "agent", [("vps-01", "reachable", 1, api_started + timedelta(seconds=20))])
    assert check_once(api_started, now=api_started + timedelta(seconds=40)) == []
    assert alerts(client, host_id="vps-01") == []


def test_watchdog_alert_resolves_when_agent_returns(client):
    create_real(client)
    t = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=10)
    post(client, "agent", [("vps-01", "reachable", 1, t)])
    for s in (30, 45, 60, 75, 90):
        check_once(t, now=t + timedelta(seconds=s))
    assert alerts(client, host_id="vps-01", status="active")
    post(client, "agent", [("vps-01", "reachable", 1, t + timedelta(seconds=s)) for s in (100, 115, 130, 145, 160)])
    [a] = alerts(client, host_id="vps-01")
    assert a["status"] == "resolved"


# ---------------------------------------------------------------- migração
def test_migration_adds_mode_to_old_database(tmp_path):
    engine = sa.create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:  # tabela no formato da etapa 4, sem a coluna mode
        conn.execute(sa.text("CREATE TABLE servers (id VARCHAR PRIMARY KEY, name VARCHAR)"))
        conn.execute(sa.text("INSERT INTO servers VALUES ('srv-a', 'srv-a')"))
    assert upgrade(engine) == ["servers.mode", "servers.last_report_at"]
    assert upgrade(engine) == []  # idempotente
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT mode FROM servers")).scalar() == "simulated"


def test_watchdog_waits_for_first_report(client):
    """Servidor recém-cadastrado que nunca enviou dados fica "sem dados", sem alerta."""
    create_real(client)
    t = datetime.now(timezone.utc)
    assert check_once(t - timedelta(minutes=10), now=t) == []
    assert client.get(f"{API}/servers/vps-01").json()["status"] == "unknown"
    assert alerts(client, host_id="vps-01") == []


def test_failed_snmp_attempt_is_not_contact(client):
    """reachable=0 vindo do coletor (timeout) não atualiza a "última coleta" do servidor."""
    create_real(client, agent=False, snmp=True)
    t = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=5)
    post(client, "snmp", [("vps-01", "cpu", 20, t), ("vps-01", "reachable", 1, t)])
    post(client, "snmp", [("vps-01", "reachable", 0, t + timedelta(seconds=s)) for s in (15, 30, 45, 60, 75)])
    host = client.get(f"{API}/servers/vps-01").json()
    assert host["last_seen_at"].startswith(t.isoformat()[:19])
    assert host["status"] == "critical" and host["metrics"]["reachable"]["value"] == 0

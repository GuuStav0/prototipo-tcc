"""Motor de gatilhos. Regra padrão de CPU: aviso > 80, crítico > 90, duração 60 s."""

from datetime import datetime, timedelta

from conftest import alerts, send, series

H = "srv-web-01"


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_spike_shorter_than_duration_does_not_fire(client, t0):
    # 45 s acima do limite (4 leituras) e depois normal
    series(client, H, "cpu", [85, 85, 85, 85, 40, 40, 40], t0)
    assert alerts(client, host_id=H) == []


def test_sustained_condition_fires_after_duration(client, t0):
    series(client, H, "cpu", [40, 85, 86, 84, 87, 88], t0)
    [a] = alerts(client, host_id=H)
    assert a["severity"] == "warning" and a["status"] == "active"
    assert a["trigger_name"] == "CPU elevada" and a["unit"] == "percent"
    assert ts(a["first_breach_at"]) == t0 + timedelta(seconds=15)
    assert ts(a["started_at"]) == t0 + timedelta(seconds=75)  # primeira violação + 60 s
    assert a["value_first"] == 88 and a["threshold"] == 80


def test_warning_escalates_to_critical_in_same_alert(client, t0):
    series(client, H, "cpu", [85] * 5 + [95] * 5, t0)
    [a] = alerts(client, host_id=H)
    assert a["severity"] == "critical" and a["peak_severity"] == "critical"
    assert a["threshold"] == 90 and a["value_peak"] == 95


def test_critical_drops_back_to_warning(client, t0):
    series(client, H, "cpu", [95] * 5 + [85] * 5, t0)
    [a] = alerts(client, host_id=H)
    assert a["status"] == "active"
    assert a["severity"] == "warning" and a["peak_severity"] == "critical"


def test_short_dip_does_not_resolve(client, t0):
    series(client, H, "cpu", [85] * 5 + [40, 40] + [85] * 3, t0)
    [a] = alerts(client, host_id=H)
    assert a["status"] == "active"


def test_resolves_after_duration_below_threshold(client, t0):
    series(client, H, "cpu", [85] * 5 + [40] * 5, t0)
    [a] = alerts(client, host_id=H)
    assert a["status"] == "resolved"
    assert ts(a["resolved_at"]) == t0 + timedelta(seconds=(5 + 4) * 15)
    assert a["value_last"] == 40


def test_new_episode_opens_new_alert(client, t0):
    series(client, H, "cpu", [85] * 5 + [40] * 5 + [85] * 5, t0)
    found = alerts(client, host_id=H)
    assert [a["status"] for a in found] == ["active", "resolved"]


def test_unreachable_host_is_critical(client, t0):
    series(client, H, "reachable", [1, 0, 0, 0, 0], t0)
    [a] = alerts(client, host_id=H)
    assert a["metric"] == "reachable" and a["severity"] == "critical"
    host = client.get(f"/api/v1/servers/{H}").json()
    assert host["status"] == "critical" and host["active_alerts"]["critical"] == 1


def test_host_specific_rule_overrides_global(client, t0):
    r = client.post("/api/v1/triggers", json={
        "name": "CPU do web-01", "metric": "cpu", "host_id": H, "operator": "gt",
        "warning_threshold": 95, "critical_threshold": 98, "duration_seconds": 30})
    assert r.status_code == 201, r.text
    # 85% dispararia a regra global, mas não a específica
    series(client, H, "cpu", [85] * 6, t0)
    assert alerts(client, host_id=H) == []
    # outros hosts continuam usando a global
    series(client, "srv-web-02", "cpu", [85] * 6, t0)
    assert len(alerts(client, host_id="srv-web-02")) == 1


def test_disabling_rule_resolves_its_alerts(client, t0):
    series(client, H, "cpu", [85] * 6, t0)
    [a] = alerts(client, host_id=H)
    r = client.patch(f"/api/v1/triggers/{a['trigger_id']}", json={"enabled": False})
    assert r.status_code == 200
    [a] = alerts(client, host_id=H)
    assert a["status"] == "resolved"


def test_out_of_order_readings_are_ignored_by_engine(client, t0):
    series(client, H, "cpu", [85] * 5, t0)  # dispara em t0+60
    # leitura antiga com valor normal não deve resolver nada
    send(client, [(H, "cpu", 10, t0 - timedelta(minutes=5))])
    [a] = alerts(client, host_id=H)
    assert a["status"] == "active"


def test_zero_duration_fires_immediately(client, t0):
    rule = next(r for r in client.get("/api/v1/triggers").json()["items"] if r["metric"] == "temp")
    client.patch(f"/api/v1/triggers/{rule['id']}", json={"duration_seconds": 0})
    series(client, H, "temp", [80], t0)
    [a] = alerts(client, host_id=H)
    assert a["severity"] == "critical" and a["first_breach_at"] == a["started_at"]

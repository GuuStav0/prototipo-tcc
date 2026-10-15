"""Testes funcionais (TCC 4.4): roda a suíte automatizada do backend e as verificações do
front-end (lint e build) e resume o resultado por área.

Uso (na pasta backend):  .venv\\Scripts\\python -m evaluation.funcional
"""

import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .comum import BACKEND_DIR, PROJECT_DIR, salvar

AREAS = {
    "test_engine.py": "Motor de gatilhos",
    "test_api.py": "API REST (servidores, métricas, alertas, relatórios, visão geral)",
    "test_assistant.py": "Assistente de IA e servidor MCP",
    "test_real_servers.py": "Servidores reais, watchdog e migração do banco",
    "test_snmp_poller.py": "Coletor SNMP (cálculos)",
    "test_influx_store.py": "InfluxDB x SQLite",
    "test_concorrencia.py": "Concorrência (muitos envios simultâneos)",
}


def main() -> None:
    xml = Path(tempfile.mkdtemp()) / "pytest.xml"
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests", f"--junitxml={xml}"],
                   cwd=BACKEND_DIR, capture_output=True)
    por_area = {}
    for caso in ET.parse(xml).getroot().iter("testcase"):
        arquivo = caso.get("classname", "").split(".")[-1] + ".py"
        area = AREAS.get(arquivo, arquivo)
        a = por_area.setdefault(area, {"total": 0, "passou": 0, "falhou": 0, "pulado": 0})
        a["total"] += 1
        if caso.find("skipped") is not None:
            a["pulado"] += 1
        elif caso.find("failure") is not None or caso.find("error") is not None:
            a["falhou"] += 1
        else:
            a["passou"] += 1

    npm = shutil.which("npm") or shutil.which("npm.cmd")
    front = {}
    for nome, cmd in (("lint (ESLint)", "lint"), ("build de produção (Vite)", "build")):
        r = subprocess.run([npm, "run", cmd], cwd=PROJECT_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
        front[nome] = "ok" if r.returncode == 0 else "falhou"

    total = {k: sum(a[k] for a in por_area.values()) for k in ("total", "passou", "falhou", "pulado")}
    for area, a in por_area.items():
        print(f"  {area:70} {a['passou']}/{a['total']}" + (f" ({a['pulado']} pulado)" if a["pulado"] else ""))
    print(f"\nbackend: {total['passou']} de {total['total']} passaram; front: {front}")
    salvar("funcional", {"backend_por_area": por_area, "backend_total": total, "frontend": front,
                         "atingiu_meta": total["falhou"] == 0 and all(v == "ok" for v in front.values())})


if __name__ == "__main__":
    main()

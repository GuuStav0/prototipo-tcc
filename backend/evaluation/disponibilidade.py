"""Teste de disponibilidade do serviço de monitoramento (TCC 4.5: 99% no período de testes).

Consulta GET /health da API a cada 15 s durante o período e calcula a porcentagem de
respostas "ok". Grava cada verificação num CSV à medida que roda: se for interrompido
(Ctrl+C ou queda de energia), os dados até ali continuam valendo.

Rode com o sistema de vocês funcionando normalmente (API na porta 8000):
    .venv\\Scripts\\python -m evaluation.disponibilidade --horas 24
"""

import argparse
import csv
import time
from datetime import datetime, timezone

import httpx

from .comum import DADOS_DIR, resumo, salvar

META = 99.0


def resumir(caminho, inicio: datetime) -> None:
    with caminho.open(encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    if not linhas:
        return
    ok = [r for r in linhas if r["ok"] == "1"]
    pct = len(ok) / len(linhas) * 100
    quedas, em_queda, inicio_q = [], False, None
    for r in linhas:
        if r["ok"] != "1" and not em_queda:
            em_queda, inicio_q = True, r["quando"]
        elif r["ok"] == "1" and em_queda:
            em_queda = False
            quedas.append({"inicio": inicio_q, "fim": r["quando"]})
    if em_queda:
        quedas.append({"inicio": inicio_q, "fim": None})
    print(f"\n{len(linhas)} verificações, {len(ok)} ok -> disponibilidade {pct:.3f}% (meta {META}%)")
    salvar("disponibilidade", {
        "meta": f"{META}% de disponibilidade durante o período de testes",
        "inicio": inicio.isoformat(timespec="seconds"),
        "horas": round((datetime.now(timezone.utc) - inicio).total_seconds() / 3600, 2),
        "verificacoes": len(linhas),
        "ok": len(ok),
        "disponibilidade_pct": round(pct, 3),
        "quedas": quedas,
        "latencia_health_ms": resumo([float(r["ms"]) for r in ok]),
        "atingiu_meta": pct >= META,
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horas", type=float, default=24)
    ap.add_argument("--api", default="http://127.0.0.1:8000/api/v1")
    ap.add_argument("--intervalo", type=float, default=15)
    a = ap.parse_args()

    DADOS_DIR.mkdir(parents=True, exist_ok=True)
    caminho = DADOS_DIR / "disponibilidade.csv"
    inicio = datetime.now(timezone.utc)
    print(f"verificando {a.api}/health a cada {a.intervalo:.0f} s por {a.horas} h (Ctrl+C encerra e gera o resumo)…")
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["quando", "ok", "ms", "detalhe"])
        fim = time.time() + a.horas * 3600
        try:
            while time.time() < fim:
                t0 = time.perf_counter()
                quando = datetime.now(timezone.utc).isoformat(timespec="seconds")
                try:
                    r = httpx.get(f"{a.api}/health", timeout=5)
                    ok = r.status_code == 200 and r.json().get("status") in ("ok", "degraded")
                    detalhe = r.json().get("status", r.status_code)
                except Exception as exc:
                    ok, detalhe = False, type(exc).__name__
                w.writerow([quando, int(ok), round((time.perf_counter() - t0) * 1000, 1), detalhe])
                f.flush()
                if not ok:
                    print(f"{quando}  FALHA: {detalhe}")
                time.sleep(max(0.0, a.intervalo - (time.perf_counter() - t0)))
        except KeyboardInterrupt:
            print("\ninterrompido")
    resumir(caminho, inicio)


if __name__ == "__main__":
    main()

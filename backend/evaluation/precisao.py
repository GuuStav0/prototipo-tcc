"""Teste de precisão dos alertas (TCC 4.5: precisão > 90%).

Gera horas de leituras sintéticas, com carimbo de tempo, para os 10 servidores e passa tudo
pela ingestão e pelo motor de gatilhos reais do SMI. Assim horas de operação cabem em segundos
e o cenário tem dezenas de eventos com resposta conhecida:

- FALHAS REAIS: 2 a 8 min acima do limite crítico -> DEVEM gerar alerta;
- PICOS CURTOS: 15 a 45 s acima do limite -> NÃO devem gerar alerta;
- RUÍDO: oscilação natural e perda de pacote (um único reachable=0) -> NÃO devem gerar alerta.

Definição usada: alerta VERDADEIRO é o que corresponde a uma falha real injetada. Alerta
gerado por pico curto, ruído, perda de pacote, ou repetido para a mesma falha, conta como FALSO.

Roda dois cenários, cada um com várias sementes aleatórias:
- TÍPICO: todos os servidores operam com folga em relação aos limites;
- EXIGENTE: 3 dos 10 servidores operam perto do limite de aviso (CPU ~72%, RAM ~76%,
  disco ~83%, temperatura ~62 °C), o que gera ruído capaz de cruzar o limite sozinho.
E, em cada um, compara durações de gatilho (0, 15, 30, 60, 120 s) com a configuração padrão.

Uso (na pasta backend):  .venv\\Scripts\\python -m evaluation.precisao
"""

import os
import random
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="smi-precisao-"))
os.environ["SMI_DATABASE_URL"] = f"sqlite:///{(_tmp / 'precisao.db').as_posix()}"
os.environ["SMI_METRICS_BACKEND"] = "sqlite"
os.environ["SMI_LLM_PROVIDER"] = "none"

from sqlalchemy import select  # noqa: E402

from app import schemas  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.ingestion import ingest  # noqa: E402
from app.metrics_store import get_metrics_store  # noqa: E402
from app.models import Alert, Trigger  # noqa: E402
from app.seed import seed  # noqa: E402

from .comum import resumo, salvar  # noqa: E402

STEP = 15            # segundos entre leituras (igual ao coletor)
HORAS = 4
N_FALHAS = 30
N_PICOS = 40
P_PERDA_PACOTE = 0.002
SEMENTES = [1, 2, 3, 4, 5]
DURACOES = [0, 15, 30, 60, 120]
PADRAO = "padrão do sistema (60 s; alcance 45 s)"

HOSTS = ["srv-web-01", "srv-web-02", "srv-db-01", "srv-db-02", "srv-app-01",
         "srv-app-02", "srv-cache-01", "srv-backup-01", "srv-mail-01", "srv-monitor-01"]
# (média, desvio) por métrica
NORMAL = {"cpu": (35, 8), "ram": (55, 3), "disk": (60, 0.3), "temp": (47, 2)}
PERTO_DO_LIMITE = {
    "srv-backup-01": {"cpu": (72, 5)},
    "srv-mail-01": {"ram": (76, 3)},
    "srv-monitor-01": {"disk": (83, 1), "temp": (62, 2)},
}
CENARIOS = {"típico": {}, "exigente": PERTO_DO_LIMITE}
VALOR_FALHA = {"cpu": (95, 2), "ram": (94, 1.5), "disk": (97, 0.5), "temp": (82, 1.5), "reachable": (0, 0)}
METRICAS = ["cpu", "ram", "disk", "temp", "reachable"]
PHI = 0.6  # autocorrelação (CPU real não salta de forma independente a cada leitura)


@dataclass
class Evento:
    host: str
    metric: str
    inicio: int  # índice da leitura
    fim: int     # índice da última leitura afetada (inclusive)
    tipo: str    # "falha" ou "pico"


def gerar_cenario(semente: int, inicio: datetime, perto: dict):
    rnd = random.Random(semente)
    passos = HORAS * 3600 // STEP
    eventos: list[Evento] = []
    ocupado: dict[tuple, list[tuple[int, int]]] = {}

    def livre(h, m, a, b):
        return all(b + 20 < x or a > y + 20 for x, y in ocupado.get((h, m), []))  # 5 min de folga

    def sortear(tipo, n, dur_min, dur_max):
        criados = 0
        while criados < n:
            h, m = rnd.choice(HOSTS), rnd.choice(METRICAS)
            dur = rnd.randint(dur_min, dur_max)
            a = rnd.randint(20, passos - dur - 20)
            if livre(h, m, a, a + dur - 1):
                ocupado.setdefault((h, m), []).append((a, a + dur - 1))
                eventos.append(Evento(h, m, a, a + dur - 1, tipo))
                criados += 1

    sortear("falha", N_FALHAS, 8, 32)   # 2 a 8 min
    sortear("pico", N_PICOS, 1, 3)      # 15 a 45 s

    ativo = {(e.host, e.metric, i): e for e in eventos for i in range(e.inicio, e.fim + 1)}
    estado = {(h, m): perto.get(h, {}).get(m, NORMAL[m])[0] for h in HOSTS for m in NORMAL}
    lotes, lote = [], []
    for i in range(passos):
        at = (inicio + timedelta(seconds=i * STEP)).isoformat()
        for h in HOSTS:
            for m in METRICAS:
                ev = ativo.get((h, m, i))
                if m == "reachable":
                    v = 0 if ev or rnd.random() < P_PERDA_PACOTE else 1
                elif ev:
                    media, desvio = VALOR_FALHA[m]
                    v = rnd.gauss(media, desvio)
                else:
                    media, desvio = perto.get(h, {}).get(m, NORMAL[m])
                    estado[(h, m)] = (media + PHI * (estado[(h, m)] - media)
                                      + rnd.gauss(0, desvio * (1 - PHI**2) ** 0.5))
                    v = estado[(h, m)]
                v = max(0.0, min(100.0, v)) if m != "temp" else v
                lote.append(schemas.Sample(host_id=h, metric=m, value=round(v, 1), collected_at=at))
        if (i + 1) % 60 == 0:  # lotes de 15 min
            lotes.append(lote)
            lote = []
    if lote:
        lotes.append(lote)
    return eventos, lotes


def rodar(duracao: int | None, eventos, lotes, inicio: datetime) -> dict:
    """duracao=None usa a configuração padrão do sistema (60 s; alcance 45 s)."""
    Base.metadata.drop_all(engine)
    seed()
    with SessionLocal() as db:
        if duracao is not None:
            for t in db.scalars(select(Trigger)):
                t.duration_seconds = duracao
            db.commit()
        store = get_metrics_store()
        for lote in lotes:
            ingest(db, store, "simulator", lote)
        alertas = db.scalars(select(Alert).order_by(Alert.started_at)).all()

    falhas = [e for e in eventos if e.tipo == "falha"]
    picos = [e for e in eventos if e.tipo == "pico"]
    t = lambda i: inicio + timedelta(seconds=i * STEP)  # noqa: E731
    usadas, vp, atrasos = set(), 0, []
    fp = {"pico_curto": 0, "ruido": 0, "repetido": 0, "perda_de_pacote": 0}
    por_sev = {"critical": [0, 0], "warning": [0, 0]}  # [verdadeiros, falsos] pela pior severidade
    for a in alertas:
        alvo = next((f for f in falhas if f.host == a.host_id and f.metric == a.metric
                     and t(f.inicio) <= a.started_at <= t(f.fim) + timedelta(seconds=(duracao or 60) + 30)), None)
        verdadeiro = alvo is not None and id(alvo) not in usadas
        por_sev[a.peak_severity][0 if verdadeiro else 1] += 1
        if verdadeiro:
            usadas.add(id(alvo))
            vp += 1
            atrasos.append((a.started_at - t(alvo.inicio)).total_seconds())
        elif alvo is not None:
            fp["repetido"] += 1
        elif any(p.host == a.host_id and p.metric == a.metric
                 and t(p.inicio) <= a.first_breach_at <= t(p.fim) + timedelta(seconds=STEP) for p in picos):
            fp["pico_curto"] += 1
        elif a.metric == "reachable":
            fp["perda_de_pacote"] += 1
        else:
            fp["ruido"] += 1
    total_fp = sum(fp.values())
    return {
        "alertas": len(alertas),
        "verdadeiros": vp,
        "falsos": total_fp,
        "falsos_por_causa": fp,
        "falhas_detectadas": len(usadas),
        "falhas_total": len(falhas),
        "precisao": round(vp / (vp + total_fp) * 100, 1) if vp + total_fp else None,
        "revocacao": round(len(usadas) / len(falhas) * 100, 1),
        "atraso_deteccao_s": resumo(atrasos),
        "por_severidade": por_sev,
    }


def consolidar(resultados: dict) -> dict:
    consolidado = {}
    for nome, runs in resultados.items():
        vp = sum(r["verdadeiros"] for r in runs)
        fp = sum(r["falsos"] for r in runs)
        det = sum(r["falhas_detectadas"] for r in runs)
        tot = sum(r["falhas_total"] for r in runs)
        atrasos = [r["atraso_deteccao_s"]["media"] for r in runs if r["atraso_deteccao_s"].get("n")]
        crit = [sum(r["por_severidade"]["critical"][i] for r in runs) for i in (0, 1)]
        precisoes = [r["precisao"] for r in runs if r["precisao"] is not None]
        consolidado[nome] = {
            "precisao": round(vp / (vp + fp) * 100, 1) if vp + fp else None,
            "precisao_min_max_por_semente": [min(precisoes), max(precisoes)] if precisoes else None,
            "precisao_criticos": round(crit[0] / sum(crit) * 100, 1) if sum(crit) else None,
            "revocacao": round(det / tot * 100, 1),
            "verdadeiros": vp,
            "falsos": fp,
            "falsos_por_causa": {k: sum(r["falsos_por_causa"][k] for r in runs) for k in runs[0]["falsos_por_causa"]},
            "atraso_medio_s": round(sum(atrasos) / len(atrasos), 1) if atrasos else None,
        }
    return consolidado


def main() -> None:
    inicio = (datetime.now(timezone.utc) - timedelta(hours=HORAS + 1)).replace(second=0, microsecond=0)
    configs = [(PADRAO, None)] + [(f"{d} s", d) for d in DURACOES]
    saida = {}
    for cenario, perto in CENARIOS.items():
        resultados = {nome: [] for nome, _ in configs}
        for semente in SEMENTES:
            eventos, lotes = gerar_cenario(semente, inicio, perto)
            print(f"\n[{cenario}] semente {semente}: {sum(len(x) for x in lotes)} leituras, "
                  f"{N_FALHAS} falhas reais, {N_PICOS} picos curtos")
            for nome, dur in configs:
                r = rodar(dur, eventos, lotes, inicio)
                resultados[nome].append(r)
                print(f"  {nome:40} precisão {r['precisao']}%  revocação {r['revocacao']}%  "
                      f"VP {r['verdadeiros']}  FP {r['falsos']}", flush=True)
        saida[cenario] = {"consolidado": consolidar(resultados), "por_semente": resultados}

    for cenario in CENARIOS:
        p = saida[cenario]["consolidado"][PADRAO]
        print(f"\n[{cenario}] PADRÃO: precisão {p['precisao']}% (por semente {p['precisao_min_max_por_semente']}), "
              f"críticos {p['precisao_criticos']}%, revocação {p['revocacao']}%")
    salvar("precisao", {
        "meta": "precisão > 90%",
        "definicao": "verdadeiro = alerta correspondente a uma falha real injetada (2 a 8 min acima do limite); "
                     "falso = alerta por pico curto (15-45 s), ruído, perda de pacote ou repetido",
        "cenario": {"horas_por_semente": HORAS, "intervalo_s": STEP, "servidores": len(HOSTS),
                    "falhas_reais_por_semente": N_FALHAS, "picos_curtos_por_semente": N_PICOS,
                    "prob_perda_pacote": P_PERDA_PACOTE, "sementes": SEMENTES,
                    "autocorrelacao_ruido": PHI, "perto_do_limite_no_exigente": PERTO_DO_LIMITE},
        "cenarios": saida,
        "atingiu_meta": {c: (saida[c]["consolidado"][PADRAO]["precisao"] or 0) > 90 for c in CENARIOS},
    })


if __name__ == "__main__":
    sys.exit(main())

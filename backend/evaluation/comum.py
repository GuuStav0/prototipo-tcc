"""Utilidades compartilhadas pelos testes da etapa 6."""

import json
import math
import platform
import statistics
from datetime import datetime, timezone
from pathlib import Path

import psutil

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
RESULTADOS_DIR = PROJECT_DIR / "docs" / "resultados"
DADOS_DIR = RESULTADOS_DIR / "dados"


def percentil(valores: list[float], p: float) -> float | None:
    """Percentil com interpolação linear (p entre 0 e 100)."""
    if not valores:
        return None
    v = sorted(valores)
    k = (len(v) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (k - lo)


def resumo(valores: list[float], casas: int = 1) -> dict:
    """n, média, desvio, mínimo, mediana, p95, máximo."""
    if not valores:
        return {"n": 0}
    r = lambda x: round(x, casas) if x is not None else None  # noqa: E731
    return {
        "n": len(valores),
        "media": r(statistics.mean(valores)),
        "desvio": r(statistics.stdev(valores)) if len(valores) > 1 else 0,
        "min": r(min(valores)),
        "mediana": r(statistics.median(valores)),
        "p95": r(percentil(valores, 95)),
        "max": r(max(valores)),
    }


def maquina() -> dict:
    """Descrição da máquina de teste (vai junto com cada resultado)."""
    freq = psutil.cpu_freq()
    return {
        "sistema": f"{platform.system()} {platform.release()}",
        "processador": platform.processor(),
        "nucleos_logicos": psutil.cpu_count(),
        "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "frequencia_mhz": round(freq.max) if freq else None,
        "python": platform.python_version(),
    }


def salvar(nome: str, dados: dict) -> Path:
    """Grava docs/resultados/dados/<nome>.json com data e máquina do teste."""
    DADOS_DIR.mkdir(parents=True, exist_ok=True)
    dados = {"teste": nome, "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "maquina": maquina(), **dados}
    destino = DADOS_DIR / f"{nome}.json"
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresultado salvo em {destino.relative_to(PROJECT_DIR)}")
    return destino


def carregar(nome: str) -> dict | None:
    caminho = DADOS_DIR / f"{nome}.json"
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else None


def parse_iso(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))

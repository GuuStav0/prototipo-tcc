"""Ambiente isolado para os testes: uma cópia completa do SMI com banco temporário.

Sobe a API (porta 8010), opcionalmente o coletor simulado e o painel (build de produção,
porta 5175), e derruba tudo ao sair, mesmo se o teste falhar. Não usa nem altera o banco,
o .env ou as portas do sistema de vocês (8000/5173).

    with Ambiente(simulador=True, historico="24h") as amb:
        amb.api.get("/servers")
"""

import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import psutil

from .comum import BACKEND_DIR, PROJECT_DIR

PYTHON = sys.executable


def _matar_arvore(proc: subprocess.Popen) -> None:
    try:
        pai = psutil.Process(proc.pid)
        for filho in pai.children(recursive=True):
            filho.kill()
        pai.kill()
    except psutil.NoSuchProcess:
        pass


class Ambiente:
    def __init__(self, porta_api: int = 8010, simulador: bool = False, historico: str | None = None,
                 painel: bool = False, porta_painel: int = 5175, llm: str = "none", semente: int = 42,
                 extra_env: dict | None = None):
        self.porta_api = porta_api
        self.simulador = simulador
        self.historico = historico
        self.painel = painel
        self.porta_painel = porta_painel
        self.llm = llm
        self.semente = semente
        self.extra_env = extra_env or {}
        self._procs: list[subprocess.Popen] = []
        self.api_url = f"http://127.0.0.1:{porta_api}/api/v1"
        self.painel_url = f"http://127.0.0.1:{porta_painel}"

    # ------------------------------------------------------------ ciclo de vida
    def __enter__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="smi-avaliacao-"))
        self.token = secrets.token_urlsafe(24)
        self.arquivo_falhas = self.dir / "faults.json"
        self.arquivo_falhas.write_text("[]", encoding="utf-8")
        self.env = {
            **os.environ,
            "SMI_DATABASE_URL": f"sqlite:///{(self.dir / 'smi.db').as_posix()}",
            "SMI_METRICS_BACKEND": "sqlite",
            "SMI_INGEST_TOKEN": self.token,
            "SMI_LLM_PROVIDER": self.llm,
            "SMI_MCP_API_URL": self.api_url,
            "SMI_COLLECTOR_API_URL": self.api_url,
            "PYTHONIOENCODING": "utf-8",
            **self.extra_env,
        }
        try:
            self._rodar([PYTHON, "-m", "app.seed", "--reset"])
            self._iniciar("api", [PYTHON, "-m", "uvicorn", "app.main:app", "--port", str(self.porta_api),
                                  "--log-level", "warning"])
            self._esperar(f"{self.api_url}/health", "API")
            self.api = httpx.Client(base_url=self.api_url + "/", timeout=60)
            if self.historico:
                print(f"gerando {self.historico} de histórico…")
                self._rodar([PYTHON, "simulator/simulate.py", "--api", self.api_url, "--token", self.token,
                             "--backfill", self.historico, "--once", "--seed", str(self.semente)])
            if self.simulador:
                self._iniciar("simulador", [PYTHON, "-u", "simulator/simulate.py", "--api", self.api_url,
                                            "--token", self.token, "--faults", str(self.arquivo_falhas),
                                            "--seed", str(self.semente)])
            if self.painel:
                self._iniciar_painel()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        for proc in reversed(self._procs):
            _matar_arvore(proc)
        self._procs.clear()
        if getattr(self, "api", None):
            self.api.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    # ------------------------------------------------------------ processos
    def _rodar(self, cmd: list[str]) -> None:
        r = subprocess.run(cmd, cwd=BACKEND_DIR, env=self.env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError(f"falhou: {' '.join(cmd)}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")

    def _iniciar(self, nome: str, cmd: list[str], cwd: Path = BACKEND_DIR, env: dict | None = None) -> subprocess.Popen:
        log = open(self.dir / f"{nome}.log", "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, cwd=cwd, env=env or self.env, stdout=log, stderr=subprocess.STDOUT)
        self._procs.append(proc)
        return proc

    def processo(self, nome: str) -> psutil.Process:
        """Processo (psutil) de um componente: 'api' ou 'simulador'.

        No Windows, o python.exe do venv é um lançador que inicia o Python de verdade como
        processo filho: devolve o de maior memória entre o lançador e os filhos."""
        idx = {"api": 0, "simulador": 1}[nome]
        pai = psutil.Process(self._procs[idx].pid)
        return max([pai, *pai.children(recursive=True)], key=lambda p: p.memory_info().rss)

    def _esperar(self, url: str, nome: str, segundos: int = 60) -> None:
        fim = time.time() + segundos
        while time.time() < fim:
            try:
                if httpx.get(url, timeout=2).status_code < 500:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise RuntimeError(f"{nome} não respondeu em {segundos} s ({url}); veja os logs em {self.dir}")

    def _iniciar_painel(self) -> None:
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        npx = shutil.which("npx") or shutil.which("npx.cmd")
        if not (PROJECT_DIR / "dist" / "index.html").exists():
            print("gerando o build de produção do painel (npm run build)…")
            subprocess.run([npm, "run", "build"], cwd=PROJECT_DIR, check=True, capture_output=True)
        env = {**self.env, "SMI_API_TARGET": f"http://127.0.0.1:{self.porta_api}"}
        self._iniciar("painel", [npx, "vite", "preview", "--port", str(self.porta_painel), "--strictPort",
                                 "--host", "127.0.0.1"], cwd=PROJECT_DIR, env=env)
        self._esperar(f"{self.painel_url}/api/v1/health", "painel")

    # ------------------------------------------------------------ falhas do simulador
    def injetar(self, falhas: list[dict]) -> None:
        """Substitui as falhas ativas no simulador: [{"host", "metric", "value"}, ...]."""
        tmp = self.arquivo_falhas.with_suffix(".tmp")
        tmp.write_text(__import__("json").dumps(falhas), encoding="utf-8")
        tmp.replace(self.arquivo_falhas)  # troca atômica: o simulador nunca lê arquivo pela metade

"""Cliente MCP: inicia o servidor MCP do SMI (python -m smi_mcp) por stdio e expõe suas
ferramentas ao agente.

A conexão fica aberta numa tarefa própria (os contextos do SDK MCP precisam abrir e fechar na
mesma tarefa) e é refeita automaticamente se o processo do servidor cair.
"""

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .providers import ToolSpec

BACKEND_DIR = Path(__file__).resolve().parents[2]
MAX_RESULT_CHARS = 6000  # resultado muito grande estoura a janela de contexto do modelo


class ToolboxUnavailable(Exception):
    pass


class MCPToolbox:
    def __init__(self, api_url: str):
        self.api_url = api_url
        self._session: ClientSession | None = None
        self._tools: list[ToolSpec] = []
        self._task: asyncio.Task | None = None
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._error: BaseException | None = None
        self._lock = asyncio.Lock()

    async def _run(self) -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "smi_mcp"],
            env={**os.environ, "SMI_API_URL": self.api_url},
            cwd=str(BACKEND_DIR),
        )
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listed = await session.list_tools()
                    self._tools = [ToolSpec(t.name, t.description or "", t.input_schema) for t in listed.tools]
                    self._session = session
                    self._ready.set()
                    await self._stop.wait()
        except asyncio.CancelledError:
            raise  # desligamento do backend
        except BaseException as exc:  # guardado para _ensure explicar a falha
            self._error = exc
        finally:
            self._session = None
            self._ready.set()

    async def _ensure(self) -> ClientSession:
        async with self._lock:
            if self._session is not None and self._task is not None and not self._task.done():
                return self._session
            self._ready, self._stop, self._error = asyncio.Event(), asyncio.Event(), None
            self._task = asyncio.create_task(self._run(), name="smi-mcp-client")
            try:
                await asyncio.wait_for(self._ready.wait(), timeout=30)
            except asyncio.TimeoutError as exc:
                raise ToolboxUnavailable("O servidor MCP não respondeu em 30 s.") from exc
            if self._session is None:
                raise ToolboxUnavailable(f"Não foi possível iniciar o servidor MCP: {self._error!r}")
            return self._session

    async def tools(self) -> list[ToolSpec]:
        await self._ensure()
        return self._tools

    async def call(self, name: str, arguments: dict) -> tuple[str, bool]:
        """Executa a ferramenta e devolve (texto para o modelo, houve_erro)."""
        session = await self._ensure()
        try:
            result = await session.call_tool(name, arguments=arguments)
        except Exception as exc:
            self._stop.set()  # força reconexão na próxima chamada
            raise ToolboxUnavailable(f"Falha na comunicação com o servidor MCP: {exc}") from exc
        text = "\n".join(getattr(c, "text", "") for c in result.content).strip() or "(sem conteúdo)"
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "\n…(resultado truncado)"
        return text, bool(result.is_error)

    async def status(self) -> tuple[bool, list[str], str]:
        try:
            tools = await self.tools()
            return True, [t.name for t in tools], ""
        except ToolboxUnavailable as exc:
            return False, [], str(exc)

    async def close(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, Exception):
                self._task.cancel()

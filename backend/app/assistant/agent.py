"""Agente do assistente (TCC 2.6 / 5.5): laço de ferramentas entre o LLM e o servidor MCP.

1. a pergunta entra no histórico da conversa;
2. o LLM responde com texto ou pede ferramentas;
3. as ferramentas rodam no servidor MCP (que consulta a API do SMI) e os resultados voltam ao LLM;
4. repete até o LLM responder só com texto (ou atingir MAX_STEPS).
"""

import asyncio
import uuid
from collections import OrderedDict
from datetime import datetime

from .providers import LLMError, Turn
from .toolbox import ToolboxUnavailable

MAX_STEPS = 8
MAX_CONVERSATIONS = 100

SYSTEM_PROMPT = """Você é o assistente de infraestrutura do SMI (Sistema de Monitoramento de Integridade para Servidores).
Você ajuda a equipe de TI a entender o estado físico dos servidores: CPU, memória, disco, temperatura e disponibilidade.

Como trabalhar:
- Responda sempre em português do Brasil, de forma objetiva.
- Antes de responder qualquer pergunta sobre servidores, métricas, alertas ou regras, consulte os dados com as ferramentas. Nunca invente valores, nomes de servidores ou horários.
- Se uma ferramenta falhar ou não houver dados, diga isso claramente.
- Estados possíveis: ok, warning (aviso), critical (crítico) e unknown (sem dados recentes).
- Ao analisar um problema, cite o servidor, a métrica, o valor atual, o limiar e há quanto tempo acontece, e verifique se há outros alertas no mesmo servidor ou no mesmo período (correlação).
- Quando houver problema, termine com recomendações práticas e curtas.
- Os horários das ferramentas já estão no horário local (dia/mês hora:minuto).
- Use Markdown simples (listas e negrito). Evite tabelas longas."""


class Assistant:
    def __init__(self, provider, toolbox):
        self.provider = provider
        self.toolbox = toolbox
        self._conversations: OrderedDict[str, list] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}

    def _history(self, conversation_id: str) -> list:
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
            while len(self._conversations) > MAX_CONVERSATIONS:
                old, _ = self._conversations.popitem(last=False)
                self._locks.pop(old, None)
        self._conversations.move_to_end(conversation_id)
        return self._conversations[conversation_id]

    async def chat(self, conversation_id: str | None, message: str) -> tuple[str, str, list[dict]]:
        """Devolve (conversation_id, resposta, ferramentas usadas)."""
        conversation_id = conversation_id or uuid.uuid4().hex
        lock = self._locks.setdefault(conversation_id, asyncio.Lock())
        async with lock:
            history = self._history(conversation_id)
            start = len(history)
            now = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M (UTC%z)")
            history.append(self.provider.user(f"[Horário local: {now}]\n{message}"))
            used: list[dict] = []
            try:
                reply = await self._loop(history, used)
            except BaseException:
                del history[start:]  # a conversa volta ao estado anterior; nada pela metade
                raise
            return conversation_id, reply, used

    async def _loop(self, history: list, used: list[dict]) -> str:
        tools = await self.toolbox.tools()
        for _ in range(MAX_STEPS):
            turn: Turn = await self.provider.complete(SYSTEM_PROMPT, history, tools)
            if turn.refused:
                raise LLMError(turn.text)
            history.append(turn.native)
            if not turn.tool_calls:
                return turn.text or "(o modelo não retornou texto)"

            results = []
            for call in turn.tool_calls:
                used.append({"name": call.name, "arguments": call.arguments})
                try:
                    text, is_error = await self.toolbox.call(call.name, call.arguments)
                except ToolboxUnavailable:
                    raise
                except Exception as exc:  # erro da ferramenta volta ao modelo, que pode se corrigir
                    text, is_error = f"Erro ao executar {call.name}: {exc}", True
                results.append((call, text, is_error))
            history.extend(self.provider.tool_results(results))

        return ("Não consegui concluir a análise dentro do limite de consultas. "
                "Tente uma pergunta mais específica (por exemplo, citando o servidor).")

    async def complete_text(self, system: str, prompt: str) -> str:
        """Pedido único, sem ferramentas (usado na análise dos relatórios)."""
        turn = await self.provider.complete(system, [self.provider.user(prompt)], [])
        if turn.refused:
            raise LLMError(turn.text)
        return turn.text

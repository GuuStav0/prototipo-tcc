"""Provedores de LLM com a mesma interface: Ollama (local, padrão) e Anthropic (Claude).

Cada provedor guarda o histórico no formato nativo da sua API; o agente só usa os métodos
abaixo (user, complete, tool_results), então o laço de ferramentas é o mesmo para os dois.
"""

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Turn:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    native: Any = None  # mensagem do assistente no formato do provedor, para o histórico
    refused: bool = False


class LLMUnavailable(Exception):
    """O provedor não está acessível ou não está configurado (vira HTTP 503)."""


class LLMError(Exception):
    """O provedor respondeu com erro (vira HTTP 502)."""


# ---------------------------------------------------------------- Ollama
class OllamaProvider:
    name = "ollama"
    MAX_HISTORY = 16  # mensagens mantidas (o modelo local tem janela pequena)

    def __init__(self, model: str, url: str, num_ctx: int, timeout: float):
        self.model = model
        self.url = url.rstrip("/")
        self.num_ctx = num_ctx
        self.timeout = timeout

    def user(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> list[dict]:
        return [{"role": "tool", "tool_name": call.name, "content": text} for call, text, _ in results]

    def _trim(self, messages: list[dict]) -> list[dict]:
        """Mantém as mensagens mais recentes, começando sempre numa mensagem do usuário."""
        if len(messages) <= self.MAX_HISTORY:
            return messages
        tail = messages[-self.MAX_HISTORY:]
        for i, m in enumerate(tail):
            if m["role"] == "user":
                return tail[i:]
        return tail

    async def complete(self, system: str, messages: list, tools: list[ToolSpec]) -> Turn:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *self._trim(messages)],
            "stream": False,
            "keep_alive": "30m",
            "options": {"num_ctx": self.num_ctx, "temperature": 0.2},
        }
        if tools:
            payload["tools"] = [
                {"type": "function",
                 "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
                for t in tools
            ]
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(f"{self.url}/api/chat", json=payload)
        except httpx.ConnectError as exc:
            raise LLMUnavailable(
                f"O Ollama não está rodando em {self.url}. Abra o aplicativo Ollama ou rode `ollama serve`."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMError(f"O modelo local demorou mais de {self.timeout:.0f} s para responder.") from exc

        if r.status_code == 404:
            raise LLMUnavailable(f"O modelo '{self.model}' não está baixado. Rode `ollama pull {self.model}`.")
        if r.status_code >= 400:
            raise LLMError(f"Ollama respondeu {r.status_code}: {r.text[:300]}")

        msg = r.json()["message"]
        calls = []
        for c in msg.get("tool_calls") or []:
            args = c["function"].get("arguments") or {}
            if isinstance(args, str):  # algumas versões devolvem JSON em texto
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(ToolCall(id=c.get("id") or uuid.uuid4().hex[:8], name=c["function"]["name"], arguments=args))
        native = {"role": "assistant", "content": msg.get("content", "")}
        if msg.get("tool_calls"):
            native["tool_calls"] = msg["tool_calls"]
        return Turn(text=msg.get("content", "").strip(), tool_calls=calls, native=native)

    async def status(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{self.url}/api/tags")
            names = {m["name"] for m in r.json().get("models", [])}
        except Exception:
            return False, f"Ollama não está rodando em {self.url}."
        if self.model in names or f"{self.model}:latest" in names:
            return True, f"Modelo local {self.model} pronto."
        return False, f"Modelo '{self.model}' não baixado. Rode `ollama pull {self.model}`."


# ---------------------------------------------------------------- Anthropic (Claude)
class AnthropicProvider:
    name = "anthropic"
    MAX_TOKENS = 16000
    # modelos com fallback no servidor (refusal -> outro modelo, na mesma chamada)
    FALLBACK_PREFIXES = ("claude-opus", "claude-sonnet", "claude-fable")

    def __init__(self, model: str, api_key: str, effort: str, timeout: float):
        import anthropic

        self._anthropic = anthropic
        self.model = model
        self.effort = effort
        self._has_key = bool(api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
        self.client = anthropic.AsyncAnthropic(api_key=api_key or None, timeout=timeout)

    def user(self, text: str) -> dict:
        return {"role": "user", "content": text}

    def tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> list[dict]:
        # todos os resultados numa única mensagem do usuário
        return [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": call.id, "content": text, "is_error": is_error}
            for call, text, is_error in results
        ]}]

    async def complete(self, system: str, messages: list, tools: list[ToolSpec]) -> Turn:
        a = self._anthropic
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.MAX_TOKENS,
            "system": system,
            "messages": messages,
        }
        if not self.model.startswith("claude-haiku-4"):  # Haiku 4.5 não aceita effort
            kwargs["output_config"] = {"effort": self.effort}
        if tools:
            kwargs["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.input_schema}
                               for t in tools]
        try:
            if self.model.startswith(self.FALLBACK_PREFIXES):
                response = await self.client.beta.messages.create(
                    **kwargs, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            else:
                response = await self.client.messages.create(**kwargs)
        except a.AuthenticationError as exc:
            raise LLMUnavailable("Chave da API da Anthropic ausente ou inválida (SMI_ANTHROPIC_API_KEY).") from exc
        except a.PermissionDeniedError as exc:
            raise LLMUnavailable(f"A chave não tem acesso ao modelo {self.model}.") from exc
        except a.RateLimitError as exc:
            raise LLMError("Limite de uso da API da Anthropic atingido; tente de novo em instantes.") from exc
        except a.APIStatusError as exc:
            raise LLMError(f"A API da Anthropic respondeu {exc.status_code}: {exc.message}") from exc
        except a.APIConnectionError as exc:
            raise LLMUnavailable("Não foi possível conectar à API da Anthropic.") from exc

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            return Turn(text="O modelo recusou esta solicitação" + (f" (categoria: {category})." if category else "."),
                        refused=True)

        text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason == "max_tokens":
            text += "\n\n_(resposta interrompida: limite de tamanho atingido)_"
        calls = [ToolCall(id=b.id, name=b.name, arguments=dict(b.input))
                 for b in response.content if b.type == "tool_use"]
        # o conteúdo volta inteiro e sem alteração (inclui blocos de raciocínio)
        return Turn(text=text, tool_calls=calls, native={"role": "assistant", "content": response.content})

    async def status(self) -> tuple[bool, str]:
        if not self._has_key:
            return False, "Defina SMI_ANTHROPIC_API_KEY (ou ANTHROPIC_API_KEY) no backend/.env."
        return True, f"Claude ({self.model}) configurado."

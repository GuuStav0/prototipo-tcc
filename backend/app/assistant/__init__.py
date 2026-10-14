"""Assistente de IA do SMI: agente com ferramentas do servidor MCP e LLM trocável."""

from functools import lru_cache

from ..config import get_settings
from .agent import Assistant
from .providers import AnthropicProvider, LLMError, LLMUnavailable, OllamaProvider
from .toolbox import MCPToolbox, ToolboxUnavailable

DEFAULT_MODELS = {"ollama": "qwen2.5:7b", "anthropic": "claude-opus-5-5"}

__all__ = ["get_assistant", "Assistant", "LLMError", "LLMUnavailable", "ToolboxUnavailable"]


def build_provider(settings=None):
    s = settings or get_settings()
    provider = s.llm_provider.lower()
    if provider in ("", "none"):
        return None
    model = s.llm_model or DEFAULT_MODELS.get(provider, "")
    if provider == "ollama":
        return OllamaProvider(model, s.ollama_url, s.ollama_num_ctx, s.llm_timeout_seconds)
    if provider == "anthropic":
        return AnthropicProvider(model, s.anthropic_api_key, s.anthropic_effort, s.llm_timeout_seconds)
    raise ValueError(f"SMI_LLM_PROVIDER inválido: {s.llm_provider!r} (use ollama, anthropic ou none)")


@lru_cache
def get_assistant() -> Assistant | None:
    """Assistente único do processo; None quando a IA está desligada (SMI_LLM_PROVIDER=none)."""
    provider = build_provider()
    if provider is None:
        return None
    return Assistant(provider, MCPToolbox(get_settings().mcp_api_url))

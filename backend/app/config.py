from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Caminhos fixos na pasta backend/: o banco e o .env são os mesmos de qualquer diretório
# de onde a API, o seed ou o simulador sejam executados.
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente com prefixo SMI_ (ou do arquivo backend/.env)."""

    model_config = SettingsConfigDict(env_prefix="SMI_", env_file=BACKEND_DIR / ".env", extra="ignore")

    # Cadastros e eventos (servidores, gatilhos, alertas, relatórios)
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'smi.db').as_posix()}"

    # Séries temporais: "sqlite" (padrão, sem dependências) ou "influx"
    metrics_backend: str = "sqlite"
    influx_url: str = "http://localhost:8086"
    influx_token: str = ""
    influx_org: str = "smi"
    influx_bucket: str = "metrics"

    # Token exigido em POST /ingest/metrics (cabeçalho X-Ingest-Token)
    ingest_token: str = "dev-token"

    # Coleta a cada 15 s; sem leitura há 3 ciclos o host fica "unknown"
    poll_interval_seconds: int = 15
    stale_after_seconds: int = 45
    # servidor real sem enviar nada por esse tempo -> o watchdog registra reachable=0 (etapa 5)
    heartbeat_timeout_seconds: int = 30

    # SLO de disponibilidade exibido no dashboard (TCC 2.5)
    slo_percent: float = 99.9

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ---------- assistente de IA (etapa 4) ----------
    # "ollama" (padrão, local e gratuito), "anthropic" (Claude, pago) ou "none" (desligado)
    llm_provider: str = "ollama"
    # vazio = padrão do provedor (qwen2.5:7b no Ollama, claude-opus-5-5 na Anthropic)
    llm_model: str = ""
    llm_timeout_seconds: float = 180
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_num_ctx: int = 8192  # janela de contexto do modelo local
    # vazio = o SDK procura ANTHROPIC_API_KEY no ambiente
    anthropic_api_key: str = ""
    anthropic_effort: str = "medium"  # low | medium | high | xhigh | max

    # Endereço da API que o servidor MCP consulta (o próprio backend)
    mcp_api_url: str = "http://127.0.0.1:8000/api/v1"
    # Endereço da API para onde o coletor SNMP envia as leituras (etapa 5)
    collector_api_url: str = "http://127.0.0.1:8000/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente com prefixo SMI_ (ou do arquivo .env)."""

    model_config = SettingsConfigDict(env_prefix="SMI_", env_file=".env", extra="ignore")

    # Cadastros e eventos (servidores, gatilhos, alertas, relatórios)
    database_url: str = "sqlite:///./smi.db"

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

    # SLO de disponibilidade exibido no dashboard (TCC 2.5)
    slo_percent: float = 99.9

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

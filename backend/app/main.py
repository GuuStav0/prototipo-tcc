from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, errors
from .assistant import get_assistant
from .config import get_settings
from .database import Base, engine
from .metrics_store import get_metrics_store
from .routers import alerts, assistant, ingest, reports, servers, system, triggers


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    get_metrics_store()  # falha cedo se SMI_METRICS_BACKEND estiver errado
    assistant = get_assistant()  # falha cedo se SMI_LLM_PROVIDER estiver errado
    yield
    if assistant is not None:
        await assistant.toolbox.close()  # encerra o processo do servidor MCP


app = FastAPI(
    title="SMI · API do Sistema de Monitoramento de Integridade",
    version=__version__,
    description="Implementação de docs/contrato/openapi.yaml",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
errors.install(app)

for module in (system, servers, triggers, alerts, reports, ingest, assistant):
    app.include_router(module.router, prefix="/api/v1")

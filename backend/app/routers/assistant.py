from fastapi import APIRouter

from ..errors import ApiError

router = APIRouter(prefix="/assistant", tags=["assistente"])


@router.post("/messages", status_code=501)
def send_message():
    # Etapa 4: o backend vai repassar a pergunta ao LLM com as ferramentas do servidor MCP.
    raise ApiError(501, "not_implemented", "o assistente de IA ainda não foi implementado (etapa 4)")

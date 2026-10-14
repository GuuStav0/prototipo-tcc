from fastapi import APIRouter, Depends

from .. import schemas
from ..assistant import Assistant, LLMError, LLMUnavailable, ToolboxUnavailable, get_assistant
from ..database import utcnow
from ..errors import ApiError

router = APIRouter(prefix="/assistant", tags=["assistente"])


def _require(assistant: Assistant | None = Depends(get_assistant)) -> Assistant:
    if assistant is None:
        raise ApiError(503, "assistant_disabled", "O assistente de IA está desligado (SMI_LLM_PROVIDER=none).")
    return assistant


@router.post("/messages", response_model=schemas.ChatResponse)
async def send_message(body: schemas.ChatRequest, assistant: Assistant = Depends(_require)):
    try:
        conversation_id, reply, used = await assistant.chat(body.conversation_id, body.message)
    except LLMUnavailable as exc:
        raise ApiError(503, "assistant_unavailable", str(exc)) from exc
    except ToolboxUnavailable as exc:
        raise ApiError(503, "mcp_unavailable", str(exc)) from exc
    except LLMError as exc:
        raise ApiError(502, "assistant_error", str(exc)) from exc
    return schemas.ChatResponse(conversation_id=conversation_id, reply=reply,
                                tool_calls=used, created_at=utcnow())


@router.get("/status", response_model=schemas.AssistantStatus)
async def status(assistant: Assistant | None = Depends(get_assistant)):
    if assistant is None:
        return schemas.AssistantStatus(
            enabled=False, provider=None, model=None, available=False,
            detail="O assistente de IA está desligado (SMI_LLM_PROVIDER=none).",
            mcp=schemas.McpStatus(connected=False, tools=[], detail=""),
        )
    available, detail = await assistant.provider.status()
    connected, tools, mcp_detail = await assistant.toolbox.status()
    return schemas.AssistantStatus(
        enabled=True, provider=assistant.provider.name, model=assistant.provider.model,
        available=available, detail=detail,
        mcp=schemas.McpStatus(connected=connected, tools=tools, detail=mcp_detail),
    )

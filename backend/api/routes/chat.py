"""Endpoint de chat com streaming SSE."""
import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.agents.rag_agent import AgentState, build_rag_graph
from backend.api.auth import get_current_user
from backend.api.schemas import ChatRequest
from backend.services.chat_service import ChatService
from backend.services.knowledge_service import KnowledgeService

logger = structlog.get_logger()
router = APIRouter()

# Instâncias singleton (em produção usar DI container)
_knowledge_service = KnowledgeService()
_chat_service = ChatService()
_rag_graph = build_rag_graph(_knowledge_service, _chat_service)


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    _user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    """
    Executa o pipeline RAG e retorna a resposta em SSE.

    Requer Bearer token válido do Azure Entra ID.
    """
    logger.info("chat_request", query_len=len(request.query), user=_user.get("sub"))

    initial_state: AgentState = {
        "query": request.query,
        "context": [],
        "sources": [],
        "response_chunks": [],
        "error": None,
    }

    async def event_stream():  # type: ignore[return]
        result = _rag_graph.invoke(initial_state)
        for chunk in result.get("response_chunks", []):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/eval/search")
async def eval_search(
    query: str,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Endpoint de avaliação para o pipeline RAGAS."""
    results = _knowledge_service.search(query)
    return {"query": query, "results": results}

"""Endpoint de chat com streaming SSE."""
import asyncio
import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse

from backend.agents.rag_agent import AgentState, build_rag_graph
from backend.api._limiter import limiter
from backend.api.auth import get_current_user, require_human_user
from backend.api.schemas import ChatRequest
from backend.services.chat_service import ChatService
from backend.services.knowledge_service import KnowledgeService

logger = structlog.get_logger()
router = APIRouter()

# Instâncias singleton (em produção usar DI container)
_knowledge_service = KnowledgeService()
_chat_service = ChatService()
_rag_graph = build_rag_graph(_knowledge_service, _chat_service)

_RAG_TIMEOUT_SECONDS = 60.0


@router.post("/chat/stream")
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    response: Response,
    body: ChatRequest,
    user: dict[str, Any] = Depends(require_human_user),
) -> StreamingResponse:
    """
    Executa o pipeline RAG e retorna a resposta em SSE.

    Requer Bearer token válido do Azure Entra ID (tokens de CI/eval rejeitados).
    Rate limit: 30 req/min por IP.
    """
    logger.info("chat_request", query_len=len(body.query), user=user.get("sub"))

    initial_state: AgentState = {
        "query": body.query,
        "context": [],
        "sources": [],
        "response_chunks": [],
        "error": None,
    }

    async def event_stream() -> None:  # type: ignore[return]
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_rag_graph.invoke, initial_state),
                timeout=_RAG_TIMEOUT_SECONDS,
            )
            for chunk in result.get("response_chunks", []):
                yield f"data: {json.dumps({'text': chunk})}\n\n"
            sources = result.get("sources", [])
            if sources:
                yield f"data: {json.dumps({'sources': sources})}\n\n"
        except asyncio.TimeoutError:
            logger.error("chat_stream_timeout", timeout=_RAG_TIMEOUT_SECONDS)
            yield f"data: {json.dumps({'error': 'Tempo limite excedido. Tente novamente.'})}\n\n"
        except Exception as exc:
            logger.error("chat_stream_error", error=str(exc), exc_info=True)
            yield f"data: {json.dumps({'error': 'Erro interno no pipeline RAG.'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/eval/search")
@limiter.limit("60/minute")
async def eval_search(
    request: Request,
    response: Response,
    query: str = Query(..., max_length=1000),
    limit: int = Query(default=5, ge=1, le=20),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Endpoint de avaliação para o pipeline RAGAS (aceita token RAGAS/eval)."""
    results = _knowledge_service.search(query, top_k=limit)
    return {"query": query, "results": results}

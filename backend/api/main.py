# backend/api/main.py
"""
AI Professor — FastAPI Backend
Endpoints REST + SSE streaming para o frontend Angular no Teams.
"""

import json
import uuid
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .auth import verify_token, UserContext
from .agents.graph import run_agent_stream
from .services.knowledge_service import KnowledgeService
from .services.conversation_service import ConversationService
from .services.dashboard_service import DashboardService
from .services.ingest_service import IngestService

app = FastAPI(
    title="AI Professor API",
    description="Backend para o agente inteligente corporativo no Microsoft Teams",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai-professor.empresa.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question:        str
    conversation_id: str
    history:         list[dict] = []


class FeedbackRequest(BaseModel):
    message_id: str
    positive:   bool
    comment:    Optional[str] = None


class TokenExchangeRequest(BaseModel):
    teams_token: str


# ─── Auth ─────────────────────────────────────────────────────────────────────

@app.post("/auth/token")
async def exchange_token(body: TokenExchangeRequest):
    """
    OBO (On-Behalf-Of) flow: troca o token do Teams por um access token
    com os grupos Entra ID do usuário.
    """
    from .auth import exchange_teams_token_obo
    result = await exchange_teams_token_obo(body.teams_token)
    return result


# ─── Chat / Streaming ─────────────────────────────────────────────────────────

@app.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    user: UserContext = Depends(verify_token),
):
    """
    Streaming SSE das respostas do Claude via LangGraph.
    Emite eventos: token | sources | done | error
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for chunk in run_agent_stream(
                question=body.question,
                conversation_id=body.conversation_id,
                history=body.history,
                user_groups=user.groups,        # filtro de permissão
                user_id=user.id,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            error_chunk = {"type": "error", "error": str(e)}
            yield f"data: {json.dumps(error_chunk)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/chat/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    user: UserContext = Depends(verify_token),
):
    """
    Registra feedback do usuário (thumbs up/down).
    Thumbs down dispara re-avaliação RAGAS do chunk correspondente.
    """
    from .services.feedback_service import FeedbackService
    await FeedbackService.record(
        message_id=body.message_id,
        user_id=user.id,
        positive=body.positive,
        comment=body.comment,
    )
    if not body.positive:
        # Dispara re-avaliação assíncrona em background
        asyncio.create_task(
            FeedbackService.trigger_reeval(body.message_id)
        )
    return {"status": "ok"}


# ─── Conversations ────────────────────────────────────────────────────────────

@app.get("/conversations")
async def list_conversations(
    page: int = 0,
    size: int = 20,
    user: UserContext = Depends(verify_token),
):
    svc = ConversationService(user_id=user.id)
    return await svc.list(page=page, size=size)


@app.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user: UserContext = Depends(verify_token),
):
    svc = ConversationService(user_id=user.id)
    conv = await svc.get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return conv


# ─── Knowledge Base ───────────────────────────────────────────────────────────

@app.get("/knowledge")
async def list_knowledge(
    user: UserContext = Depends(verify_token),
):
    """Lista todos os documentos indexados visíveis para o usuário."""
    svc = KnowledgeService()
    return await svc.list_items(user_groups=user.groups)


@app.get("/knowledge/search")
async def search_knowledge(
    q: str,
    top: int = 10,
    user: UserContext = Depends(verify_token),
):
    """Busca híbrida na base de conhecimento com filtro de permissão."""
    svc = KnowledgeService()
    return await svc.search(query=q, user_groups=user.groups, top=top)


# ─── Ingest / Upload ──────────────────────────────────────────────────────────

@app.post("/ingest/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: UserContext = Depends(verify_token),
):
    """
    Recebe arquivo do Angular Upload Component.
    Salva no Blob Storage e dispara o pipeline de ingestão.
    """
    job_id = str(uuid.uuid4())
    svc = IngestService()
    await svc.start_pipeline(
        file=file,
        job_id=job_id,
        uploaded_by=user.id,
    )
    return {"job_id": job_id, "status": "queued"}


@app.get("/ingest/status/{job_id}")
async def ingest_status(
    job_id: str,
    user: UserContext = Depends(verify_token),
):
    """Polling de status do pipeline de ingestão (chamado pelo Angular)."""
    svc = IngestService()
    status = await svc.get_status(job_id)
    return status


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/dashboard/metrics")
async def dashboard_metrics(
    user: UserContext = Depends(verify_token),
):
    """
    Métricas agregadas para o DashboardComponent Angular.
    Requer perfil de administrador ou gestor.
    """
    if "ai-professor-admins" not in user.groups and "ai-professor-managers" not in user.groups:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    svc = DashboardService()
    return await svc.get_metrics()


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status":    "healthy",
        "version":   "3.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }

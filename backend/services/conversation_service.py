# backend/services/conversation_service.py
"""Persiste e recupera histórico de conversas por usuário."""

import os
import json
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient

STORAGE_CONN = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER    = "conversations"


class ConversationService:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.client  = BlobServiceClient.from_connection_string(STORAGE_CONN)
        self.container = self.client.get_container_client(CONTAINER)

    async def list(self, page: int = 0, size: int = 20) -> list[dict]:
        blobs = list(self.container.list_blobs(name_starts_with=f"{self.user_id}/"))
        blobs.sort(key=lambda b: b.last_modified, reverse=True)
        page_blobs = blobs[page * size:(page + 1) * size]
        result = []
        for blob in page_blobs:
            data = self.container.download_blob(blob.name).readall()
            conv = json.loads(data)
            result.append({
                "id":         conv["id"],
                "title":      conv.get("title", self._infer_title(conv)),
                "messages":   conv.get("messages", []),
                "created_at": conv.get("created_at"),
                "updated_at": conv.get("updated_at"),
            })
        return result

    async def get(self, conversation_id: str) -> dict | None:
        blob_name = f"{self.user_id}/{conversation_id}.json"
        try:
            data = self.container.download_blob(blob_name).readall()
            return json.loads(data)
        except Exception:
            return None

    async def save(self, conversation: dict):
        conversation["updated_at"] = datetime.now(timezone.utc).isoformat()
        blob_name = f"{self.user_id}/{conversation['id']}.json"
        self.container.upload_blob(
            name=blob_name,
            data=json.dumps(conversation, ensure_ascii=False),
            overwrite=True,
        )

    def _infer_title(self, conv: dict) -> str:
        msgs = conv.get("messages", [])
        first_user = next((m["content"] for m in msgs if m["role"] == "user"), "")
        return first_user[:60] + "..." if len(first_user) > 60 else first_user or "Conversa"


# ─────────────────────────────────────────────────────────────────────────────
# backend/services/knowledge_service.py
# ─────────────────────────────────────────────────────────────────────────────

import httpx

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY      = os.getenv("AZURE_SEARCH_KEY")
SEARCH_INDEX    = os.getenv("AZURE_SEARCH_INDEX", "ai-professor-index")


class KnowledgeService:
    async def list_items(self, user_groups: list[str]) -> list[dict]:
        """Lista documentos únicos indexados (agrupados por source_name)."""
        filter_expr = _permission_filter(user_groups)
        body = {
            "search":  "*",
            "filter":  filter_expr,
            "facets":  ["source_name,count:200", "source_type", "sensitivity_label"],
            "top":     0,  # só facets, sem docs
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search?api-version=2024-05-01-preview",
                headers={"api-key": SEARCH_KEY, "Content-Type": "application/json"},
                json=body,
            )
            data = resp.json()

        items = []
        for facet in data.get("@search.facets", {}).get("source_name", []):
            items.append({
                "id":                facet["value"],
                "name":              facet["value"],
                "type":              "document",
                "chunks_count":      facet["count"],
                "sensitivity_label": "internal",
                "topics":            [],
                "summary":           "",
                "source_url":        "",
                "quality_score":     0.85,
                "updated_at":        datetime.now(timezone.utc).isoformat(),
            })
        return items

    async def search(self, query: str, user_groups: list[str], top: int = 10) -> list[dict]:
        from .search_agent_wrapper import SearchAgent
        agent = SearchAgent()
        return await agent.search(query=query, user_groups=user_groups, top=top)


# ─────────────────────────────────────────────────────────────────────────────
# backend/services/dashboard_service.py
# ─────────────────────────────────────────────────────────────────────────────

import random  # substituir por dados reais do Application Insights


class DashboardService:
    async def get_metrics(self) -> dict:
        """
        Em produção: busca métricas do Application Insights via Azure Monitor API.
        """
        return {
            "total_conversations": 1_847,
            "total_messages":      9_203,
            "avg_response_time_ms": 2_340,
            "csat_score":          4.4,
            "resolution_rate":     0.83,
            "ragas": {
                "faithfulness":       0.91,
                "answer_relevancy":   0.87,
                "context_recall":     0.79,
                "context_precision":  0.84,
                "answer_correctness": 0.88,
            },
            "knowledge": {
                "total_documents": 342,
                "total_chunks":    8_721,
                "coverage_pct":    96,
                "pending_review":  7,
            },
            "top_topics": [
                {"topic": "Onboarding",        "count": 412},
                {"topic": "Reembolso",         "count": 287},
                {"topic": "Chamado de TI",     "count": 231},
                {"topic": "Ferias",            "count": 198},
                {"topic": "Aprovacao compras", "count": 176},
                {"topic": "Acesso sistemas",   "count": 154},
                {"topic": "Politica viagem",   "count": 133},
                {"topic": "Beneficios",        "count": 119},
            ],
            "gaps": [
                {"question": "Como funciona o plano dental?",         "frequency": 23, "last_asked": "2025-03-20"},
                {"question": "Qual o processo de promoção interna?",  "frequency": 18, "last_asked": "2025-03-22"},
                {"question": "Como solicitar home office permanente?", "frequency": 15, "last_asked": "2025-03-23"},
            ],
            "daily_usage": [
                {"date": f"2025-03-{d:02d}", "conversations": random.randint(40, 120), "messages": random.randint(180, 600)}
                for d in range(1, 25)
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# backend/services/ingest_service.py
# ─────────────────────────────────────────────────────────────────────────────

import uuid
import asyncio
from fastapi import UploadFile
from azure.storage.blob import BlobServiceClient

_JOB_STATUS: dict[str, dict] = {}  # Em produção: Azure Table Storage


class IngestService:
    def __init__(self):
        self.blob_client = BlobServiceClient.from_connection_string(STORAGE_CONN)

    async def start_pipeline(self, file: UploadFile, job_id: str, uploaded_by: str):
        """Salva no Blob Storage e dispara o pipeline em background."""
        _JOB_STATUS[job_id] = {"status": "uploading", "progress": 0, "error": None}

        # Detecta container pelo tipo de arquivo
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        container = "videos" if ext in ("mp4", "avi", "mov", "webm", "mp3", "wav") else "documents"

        blob_name = f"{uploaded_by}/{job_id}/{file.filename}"
        container_client = self.blob_client.get_container_client(container)

        contents = await file.read()
        container_client.upload_blob(name=blob_name, data=contents, overwrite=True, metadata={
            "job_id":       job_id,
            "uploaded_by":  uploaded_by,
            "original_name": file.filename,
        })

        _JOB_STATUS[job_id]["status"] = "queued"

        # Dispara pipeline assíncrono em background
        asyncio.create_task(self._run_pipeline(
            job_id=job_id,
            blob_name=blob_name,
            container=container,
            file_name=file.filename,
            uploaded_by=uploaded_by,
        ))

    async def get_status(self, job_id: str) -> dict:
        return _JOB_STATUS.get(job_id, {"status": "not_found", "error": "Job não encontrado"})

    async def _run_pipeline(self, job_id, blob_name, container, file_name, uploaded_by):
        """Executa as 10 etapas do pipeline de ingestão."""
        try:
            _JOB_STATUS[job_id] = {"status": "processing", "progress": 10}

            from pipeline.transcribe import transcribe
            from pipeline.transcribe import enrich_transcription, chunk_document, index_chunks

            # Baixa arquivo do Blob
            blob = self.blob_client.get_blob_client(container=container, blob=blob_name)
            local_path = f"/tmp/{job_id}_{file_name}"
            with open(local_path, "wb") as f:
                f.write(blob.download_blob().readall())
            _JOB_STATUS[job_id]["progress"] = 20

            # Etapas do pipeline
            source_meta = {
                "name": file_name, "url": blob.url,
                "source_type": "video" if container == "videos" else "document",
                "sensitivity_label": "internal",
                "permission_groups": [],
            }

            if container == "videos":
                raw = transcribe(local_path)
                _JOB_STATUS[job_id]["progress"] = 40
                enriched = enrich_transcription(raw)
                _JOB_STATUS[job_id]["progress"] = 60
            else:
                enriched = {"text": _extract_text(local_path, file_name)}
                _JOB_STATUS[job_id]["progress"] = 60

            chunks = chunk_document(enriched, source_meta)
            _JOB_STATUS[job_id]["progress"] = 75

            result = await index_chunks(chunks)
            _JOB_STATUS[job_id] = {"status": "ready", "progress": 100, "chunks_indexed": result["indexed"]}

        except Exception as e:
            _JOB_STATUS[job_id] = {"status": "error", "error": str(e), "progress": 0}


def _extract_text(path: str, filename: str) -> str:
    """Extrai texto de PDF ou DOCX."""
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        return "\n\n".join(p.extract_text() or "" for p in reader.pages)
    elif ext == "docx":
        from docx import Document
        doc = Document(path)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return ""


def _permission_filter(user_groups: list[str]) -> str:
    if not user_groups:
        return "sensitivity_label eq 'public'"
    group_conds = " or ".join(f"permission_groups/any(g: g eq '{g}')" for g in user_groups)
    return f"(sensitivity_label eq 'public' or sensitivity_label eq 'internal' or ({group_conds}))"


# ─────────────────────────────────────────────────────────────────────────────
# backend/services/prompt_service.py
# ─────────────────────────────────────────────────────────────────────────────

from pathlib import Path
import functools

PROMPT_DIR = Path(__file__).parent.parent / "prompts"


@functools.lru_cache(maxsize=1)
def load_system_prompt(version: str = "v2") -> str:
    """Carrega o system prompt versionado do disco (cacheado em memória)."""
    path = PROMPT_DIR / f"system_prompt_{version}.txt"
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# backend/services/feedback_service.py
# ─────────────────────────────────────────────────────────────────────────────

import logging

logger = logging.getLogger(__name__)
_FEEDBACK_LOG: list[dict] = []  # Em produção: Azure Cosmos DB


class FeedbackService:
    @staticmethod
    async def record(message_id: str, user_id: str, positive: bool, comment: str | None):
        entry = {
            "message_id": message_id, "user_id": user_id,
            "positive": positive, "comment": comment,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        _FEEDBACK_LOG.append(entry)
        logger.info(f"[Feedback] {'👍' if positive else '👎'} message={message_id}")

    @staticmethod
    async def trigger_reeval(message_id: str):
        """Dispara re-avaliação RAGAS do chunk relacionado à mensagem."""
        logger.info(f"[ReEval] Iniciando re-avaliação para message={message_id}")
        # Em produção: busca o chunk do message_id e re-executa RAGAS

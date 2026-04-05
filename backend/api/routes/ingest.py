"""Endpoints de ingestão de vídeo/áudio."""
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel

from backend.api.auth import get_current_user
from backend.services.blob_service import BlobService
from backend.services.ingest_service import IngestService

logger = structlog.get_logger()
router = APIRouter()

_ingest_service = IngestService()
_blob_service = BlobService()

ALLOWED_EXTENSIONS = {".mkv", ".mp4", ".mp3", ".wav", ".m4a", ".webm"}
MAX_FILE_SIZE_MB = 1024

# Armazena status dos jobs em memória (suficiente para instância única)
_jobs: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# POST /ingest — upload direto (mantido para compatibilidade)
# ---------------------------------------------------------------------------

@router.post("/ingest")
async def ingest_video(
    file: UploadFile,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Recebe vídeo/áudio, transcreve via AssemblyAI e indexa no Qdrant."""
    import os

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {ext}. Use: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    file_bytes = await file.read()
    size_mb = len(file_bytes) / (1024 * 1024)

    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo muito grande: {size_mb:.1f}MB. Máximo: {MAX_FILE_SIZE_MB}MB",
        )

    logger.info("ingest_request", filename=file.filename, size_mb=round(size_mb, 1))

    try:
        result = _ingest_service.ingest(file_bytes, file.filename or "upload")
    except Exception as exc:
        logger.error("ingest_error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Erro na ingestão: {exc}") from exc

    return {
        "status": "ok",
        "filename": result["filename"],
        "n_chunks": result["n_chunks"],
        "duration_sec": result["duration_sec"],
        "message": f"{result['n_chunks']} chunks indexados com sucesso.",
    }


# ---------------------------------------------------------------------------
# GET /ingest/sas-token — gera SAS URL para upload direto ao Blob Storage
# ---------------------------------------------------------------------------

@router.get("/ingest/sas-token")
async def get_sas_token(
    filename: str = Query(..., description="Nome do arquivo a ser enviado"),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """Retorna SAS URL de escrita para upload direto ao Azure Blob Storage."""
    import os

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {ext}. Use: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    try:
        upload_url, blob_name = _blob_service.generate_upload_sas(filename)
    except Exception as exc:
        logger.error("sas_token_error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Erro ao gerar SAS token: {exc}") from exc

    logger.info("sas_token_issued", filename=filename, blob_name=blob_name)
    return {"upload_url": upload_url, "blob_name": blob_name}


# ---------------------------------------------------------------------------
# POST /ingest/process — dispara processamento em background e retorna job_id
# ---------------------------------------------------------------------------

class ProcessRequest(BaseModel):
    blob_name: str
    original_filename: str


@router.post("/ingest/process")
async def process_blob(
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Registra job e inicia transcrição + indexação em background.

    Retorna imediatamente com job_id para polling via GET /ingest/status/{job_id}.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "processing"}

    background_tasks.add_task(
        _run_ingest,
        job_id=job_id,
        blob_name=body.blob_name,
        original_filename=body.original_filename,
    )

    logger.info("process_job_started", job_id=job_id, blob_name=body.blob_name)
    return {"job_id": job_id, "status": "processing"}


def _run_ingest(job_id: str, blob_name: str, original_filename: str) -> None:
    """Executado em background: transcreve via URL SAS e indexa no Qdrant."""
    try:
        read_url = _blob_service.get_read_url(blob_name)
        result = _ingest_service.ingest_from_url(read_url, original_filename)
        _jobs[job_id] = {"status": "done", "result": result}
        logger.info("process_job_done", job_id=job_id, n_chunks=result["n_chunks"])
    except Exception as exc:
        _jobs[job_id] = {"status": "error", "error": str(exc)}
        logger.error("process_job_error", job_id=job_id, error=str(exc))
    finally:
        _blob_service.delete_blob(blob_name)


# ---------------------------------------------------------------------------
# GET /ingest/status/{job_id} — consulta status do job
# ---------------------------------------------------------------------------

@router.get("/ingest/status/{job_id}")
async def get_job_status(
    job_id: str,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Retorna status do job: processing | done | error."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")

    if job["status"] == "done":
        r = job["result"]
        return {
            "status": "done",
            "filename": r["filename"],
            "n_chunks": r["n_chunks"],
            "duration_sec": r["duration_sec"],
            "message": f"{r['n_chunks']} chunks indexados com sucesso.",
        }

    if job["status"] == "error":
        raise HTTPException(status_code=500, detail=job["error"])

    return {"status": "processing"}

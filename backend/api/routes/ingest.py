"""Endpoints de ingestão de vídeo/áudio."""
import os
import threading
import time
import uuid
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field, field_validator

from backend.api._limiter import limiter
from backend.api.auth import require_human_user
from backend.services.blob_service import BlobService
from backend.services.ingest_service import IngestService

logger = structlog.get_logger()
router = APIRouter()

_ingest_service = IngestService()
_blob_service = BlobService()

ALLOWED_EXTENSIONS = {".mkv", ".mp4", ".mp3", ".wav", ".m4a", ".webm"}
MAX_FILE_SIZE_BYTES = 1024 * 1024 * 1024  # 1 GB

# Magic bytes de formatos de áudio/vídeo suportados
_AUDIO_VIDEO_MAGIC: list[bytes] = [
    b"\x00\x00\x00\x18ftyp",  # MP4 (ftyp box)
    b"\x00\x00\x00\x1cftyp",  # MP4 variant
    b"\x00\x00\x00 ftyp",     # MP4 variant
    b"\x00\x00\x00\x14ftyp",  # MP4 variant
    b"ID3",                    # MP3 com tag ID3
    b"\xff\xfb",               # MP3 frame sync
    b"\xff\xf3",               # MP3 frame sync
    b"\xff\xf2",               # MP3 frame sync
    b"RIFF",                   # WAV / WebM
    b"\x1aE\xdf\xa3",          # MKV / WebM
    b"fLaC",                   # FLAC
]


def _has_valid_magic_bytes(data: bytes) -> bool:
    """Verifica se os primeiros bytes correspondem a um formato de áudio/vídeo válido."""
    header = data[:12]
    return any(header[: len(magic)] == magic for magic in _AUDIO_VIDEO_MAGIC)

# Armazena status dos jobs em memória (suficiente para instância única)
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_JOB_TTL_SECONDS = 3600  # Remove jobs concluídos após 1 hora


def _cleanup_stale_jobs() -> None:
    """Remove jobs finalizados (done/error) mais antigos que o TTL."""
    now = time.monotonic()
    with _jobs_lock:
        stale = [
            jid
            for jid, j in _jobs.items()
            if j["status"] != "processing"
            and now - j.get("_created_at", now) > _JOB_TTL_SECONDS
        ]
        for jid in stale:
            del _jobs[jid]


# ---------------------------------------------------------------------------
# POST /ingest — upload direto (mantido para compatibilidade)
# ---------------------------------------------------------------------------


@router.post("/ingest")
@limiter.limit("3/minute")
async def ingest_video(
    request: Request,
    response: Response,
    file: UploadFile,
    _user: dict[str, Any] = Depends(require_human_user),
) -> dict[str, Any]:
    """Recebe vídeo/áudio, transcreve via AssemblyAI e indexa no Qdrant."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {ext}. Use: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Rejeita antes de ler se Content-Length já excede o limite
    if file.size is not None and file.size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo muito grande. Máximo: {MAX_FILE_SIZE_BYTES // (1024*1024)}MB",
        )

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Arquivo muito grande: {len(file_bytes) // (1024*1024)}MB. "
            f"Máximo: {MAX_FILE_SIZE_BYTES // (1024*1024)}MB",
        )

    if not _has_valid_magic_bytes(file_bytes):
        raise HTTPException(
            status_code=415,
            detail="Tipo de arquivo inválido. O conteúdo não corresponde a um formato de áudio/vídeo suportado.",
        )

    logger.info(
        "ingest_request",
        filename=file.filename,
        size_mb=round(len(file_bytes) / (1024 * 1024), 1),
    )

    try:
        result = _ingest_service.ingest(file_bytes, file.filename or "upload")
    except Exception as exc:
        logger.error("ingest_error", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao processar arquivo.") from exc

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
@limiter.limit("10/minute")
async def get_sas_token(
    request: Request,
    response: Response,
    filename: str = Query(..., description="Nome do arquivo a ser enviado"),
    _user: dict[str, Any] = Depends(require_human_user),
) -> dict[str, str]:
    """Retorna SAS URL de escrita para upload direto ao Azure Blob Storage."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {ext}. Use: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    try:
        upload_url, blob_name = _blob_service.generate_upload_sas(filename)
    except Exception as exc:
        logger.error("sas_token_error", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao gerar URL de upload.") from exc

    logger.info("sas_token_issued", filename=filename, blob_name=blob_name)
    return {"upload_url": upload_url, "blob_name": blob_name}


# ---------------------------------------------------------------------------
# POST /ingest/process — dispara processamento em background e retorna job_id
# ---------------------------------------------------------------------------


class ProcessRequest(BaseModel):
    blob_name: str = Field(..., max_length=512)
    original_filename: str = Field(..., max_length=256)

    @field_validator("blob_name")
    @classmethod
    def validate_blob_name(cls, v: str) -> str:
        # Formato esperado: {uuid}/{filename} — no máximo uma barra, sem traversal
        if ".." in v or v.startswith("/") or v.endswith("/") or v.count("/") > 1 or "\\" in v:
            raise ValueError("blob_name inválido: formato não permitido.")
        return v


@router.post("/ingest/process")
@limiter.limit("5/minute")
async def process_blob(
    request: Request,
    response: Response,
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    _user: dict[str, Any] = Depends(require_human_user),
) -> dict[str, Any]:
    """
    Registra job e inicia transcrição + indexação em background.

    Retorna imediatamente com job_id para polling via GET /ingest/status/{job_id}.
    """
    _cleanup_stale_jobs()

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {"status": "processing", "_created_at": time.monotonic()}

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
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "done",
                "result": result,
                "_created_at": _jobs.get(job_id, {}).get("_created_at", time.monotonic()),
            }
        logger.info("process_job_done", job_id=job_id, n_chunks=result["n_chunks"])
    except Exception as exc:
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "error": str(exc),
                "_created_at": _jobs.get(job_id, {}).get("_created_at", time.monotonic()),
            }
        logger.error("process_job_error", job_id=job_id, error=str(exc), exc_info=True)
    finally:
        try:
            _blob_service.delete_blob(blob_name)
        except Exception as del_exc:
            logger.warning("blob_delete_failed", blob_name=blob_name, error=str(del_exc))


# ---------------------------------------------------------------------------
# GET /ingest/status/{job_id} — consulta status do job
# ---------------------------------------------------------------------------


@router.get("/ingest/status/{job_id}")
async def get_job_status(
    job_id: str,
    _user: dict[str, Any] = Depends(require_human_user),
) -> dict[str, Any]:
    """Retorna status do job: processing | done | error."""
    with _jobs_lock:
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

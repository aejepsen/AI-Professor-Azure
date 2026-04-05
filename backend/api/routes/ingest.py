"""Endpoint de ingestão de vídeo/áudio."""
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from backend.api.auth import get_current_user
from backend.services.ingest_service import IngestService

logger = structlog.get_logger()
router = APIRouter()

_ingest_service = IngestService()

ALLOWED_EXTENSIONS = {".mkv", ".mp4", ".mp3", ".wav", ".m4a", ".webm"}
MAX_FILE_SIZE_MB = 1024


@router.post("/ingest")
async def ingest_video(
    file: UploadFile,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Recebe vídeo/áudio, transcreve via AssemblyAI e indexa no Qdrant.

    Requer Bearer token válido do Azure Entra ID.
    """
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

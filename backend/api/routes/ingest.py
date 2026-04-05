"""Endpoints de ingestão de vídeo/áudio."""
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
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


# ---------------------------------------------------------------------------
# POST /ingest — upload direto (mantido para compatibilidade)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# GET /ingest/sas-token — gera SAS URL para upload direto ao Blob Storage
# ---------------------------------------------------------------------------

@router.get("/ingest/sas-token")
async def get_sas_token(
    filename: str = Query(..., description="Nome do arquivo a ser enviado"),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, str]:
    """
    Retorna uma SAS URL de escrita para o Azure Blob Storage.

    O frontend usa essa URL para enviar o arquivo diretamente ao blob,
    sem passar pelo backend, obtendo progresso de upload real.
    """
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
# POST /ingest/process — dispara transcrição a partir do blob já enviado
# ---------------------------------------------------------------------------

class ProcessRequest(BaseModel):
    blob_name: str
    original_filename: str


@router.post("/ingest/process")
async def process_blob(
    body: ProcessRequest,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Gera SAS de leitura, aciona AssemblyAI via URL e indexa no Qdrant.

    Após o processamento, o blob é deletado.
    """
    logger.info("process_blob_start", blob_name=body.blob_name, filename=body.original_filename)

    try:
        read_url = _blob_service.get_read_url(body.blob_name)
        result = _ingest_service.ingest_from_url(read_url, body.original_filename)
    except Exception as exc:
        logger.error("process_blob_error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Erro no processamento: {exc}") from exc
    finally:
        _blob_service.delete_blob(body.blob_name)

    return {
        "status": "ok",
        "filename": result["filename"],
        "n_chunks": result["n_chunks"],
        "duration_sec": result["duration_sec"],
        "message": f"{result['n_chunks']} chunks indexados com sucesso.",
    }

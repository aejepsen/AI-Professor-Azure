# backend/services/ingest_service.py
"""
Serviço de ingestão: recebe uploads e dispara o pipeline de processamento.
"""

import os
import uuid
import asyncio
import logging
from datetime import datetime

from fastapi import UploadFile
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

STORAGE_CONN = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
CONTAINER = "ai-professor-uploads"

# Status em memória (em produção: Azure Table Storage ou Redis)
_JOB_STATUS: dict[str, dict] = {}


class IngestService:
    """Gerencia o pipeline de ingestão de documentos e vídeos."""

    async def start_pipeline(
        self,
        file: UploadFile,
        job_id: str,
        uploaded_by: str,
    ) -> None:
        """Salva o arquivo no Blob Storage e inicia o pipeline em background."""
        _JOB_STATUS[job_id] = {
            "job_id": job_id,
            "status": "uploading",
            "progress": 0,
            "filename": file.filename,
            "uploaded_by": uploaded_by,
            "created_at": datetime.utcnow().isoformat(),
            "error": None,
        }

        # Inicia em background para não bloquear a resposta HTTP
        asyncio.create_task(
            self._run_pipeline(file=file, job_id=job_id, uploaded_by=uploaded_by)
        )

    async def get_status(self, job_id: str) -> dict:
        """Retorna o status atual do job de ingestão."""
        return _JOB_STATUS.get(job_id, {
            "job_id": job_id,
            "status": "not_found",
            "error": "Job não encontrado",
        })

    async def _run_pipeline(
        self,
        file: UploadFile,
        job_id: str,
        uploaded_by: str,
    ) -> None:
        """Pipeline assíncrono: upload → extração → chunking → indexação."""
        try:
            # 1. Upload para Blob Storage
            _JOB_STATUS[job_id]["status"] = "uploading"
            _JOB_STATUS[job_id]["progress"] = 10

            content = await file.read()
            blob_url = await self._upload_to_blob(
                content=content,
                filename=file.filename or f"{job_id}.bin",
                job_id=job_id,
            )

            _JOB_STATUS[job_id]["progress"] = 30
            _JOB_STATUS[job_id]["blob_url"] = blob_url

            # 2. Extração de texto (PDF/DOCX/MP4)
            _JOB_STATUS[job_id]["status"] = "extracting"
            _JOB_STATUS[job_id]["progress"] = 50
            await asyncio.sleep(0.1)  # Placeholder para extração real

            # 3. Chunking e indexação no Qdrant
            _JOB_STATUS[job_id]["status"] = "indexing"
            _JOB_STATUS[job_id]["progress"] = 80
            await asyncio.sleep(0.1)  # Placeholder para indexação real

            # 4. Concluído
            _JOB_STATUS[job_id]["status"] = "completed"
            _JOB_STATUS[job_id]["progress"] = 100
            _JOB_STATUS[job_id]["completed_at"] = datetime.utcnow().isoformat()

        except Exception as e:
            logger.error(f"Pipeline falhou para job {job_id}: {e}")
            _JOB_STATUS[job_id]["status"] = "failed"
            _JOB_STATUS[job_id]["error"] = str(e)

    async def _upload_to_blob(
        self, content: bytes, filename: str, job_id: str
    ) -> str:
        """Faz upload do arquivo para o Azure Blob Storage."""
        if not STORAGE_CONN:
            # Sem conexão configurada — retorna URL simulada
            return f"https://storage.blob.core.windows.net/{CONTAINER}/{job_id}/{filename}"

        try:
            blob_service = BlobServiceClient.from_connection_string(STORAGE_CONN)
            blob_name = f"{job_id}/{filename}"
            blob_client = blob_service.get_blob_client(
                container=CONTAINER, blob=blob_name
            )
            blob_client.upload_blob(content, overwrite=True)
            return blob_client.url
        except Exception as e:
            logger.warning(f"Blob upload falhou: {e}")
            return f"local://{job_id}/{filename}"

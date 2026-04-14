"""Serviço de Azure Blob Storage — gera SAS tokens e gerencia blobs."""
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    generate_blob_sas,
)

from backend.core.config import settings

logger = structlog.get_logger()


class BlobService:
    def __init__(self) -> None:
        self._account_name = settings.azure_storage_account_name
        self._account_key = settings.azure_storage_account_key
        self._container = settings.azure_storage_container
        self._client = BlobServiceClient(
            account_url=f"https://{self._account_name}.blob.core.windows.net",
            credential=self._account_key,
        )

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Remove path traversal, null bytes e caracteres especiais do filename."""
        name = os.path.basename(filename)  # strip path separators
        name = name.replace("\x00", "")  # null bytes
        name = re.sub(r"[^\w\s\-.]", "_", name)  # apenas alfanum, dash, dot, underscore
        name = name.strip(". ")  # remove leading/trailing dots e espaços
        return name[:255] if name else "upload"

    def generate_upload_sas(self, filename: str) -> tuple[str, str]:
        """Gera SAS URL de escrita e retorna (upload_url, blob_name).

        O blob_name inclui um UUID para evitar colisões.
        A SAS expira em 2 horas.
        """
        safe_filename = self._sanitize_filename(filename)
        blob_name = f"{uuid.uuid4()}/{safe_filename}"
        expiry = datetime.now(tz=timezone.utc) + timedelta(hours=2)

        sas_token = generate_blob_sas(
            account_name=self._account_name,
            container_name=self._container,
            blob_name=blob_name,
            account_key=self._account_key,
            permission=BlobSasPermissions(create=True, write=True),
            expiry=expiry,
        )

        upload_url = (
            f"https://{self._account_name}.blob.core.windows.net"
            f"/{self._container}/{blob_name}?{sas_token}"
        )
        logger.info("sas_generated", blob_name=blob_name, expiry=expiry.isoformat())
        return upload_url, blob_name

    def get_read_url(self, blob_name: str) -> str:
        """Gera SAS URL de leitura válida por 4 horas (para AssemblyAI)."""
        expiry = datetime.now(tz=timezone.utc) + timedelta(hours=4)

        sas_token = generate_blob_sas(
            account_name=self._account_name,
            container_name=self._container,
            blob_name=blob_name,
            account_key=self._account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry,
        )

        return (
            f"https://{self._account_name}.blob.core.windows.net"
            f"/{self._container}/{blob_name}?{sas_token}"
        )

    def delete_blob(self, blob_name: str) -> None:
        """Remove o blob após a transcrição ser concluída."""
        try:
            blob_client = self._client.get_blob_client(
                container=self._container, blob=blob_name
            )
            blob_client.delete_blob()
            logger.info("blob_deleted", blob_name=blob_name)
        except Exception as exc:
            logger.warning("blob_delete_failed", blob_name=blob_name, error=str(exc))

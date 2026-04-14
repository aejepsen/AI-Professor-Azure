"""Endpoint de health check com verificação de dependências."""
import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from backend.core.config import settings

logger = structlog.get_logger()
router = APIRouter()


@router.get("/health")
async def health() -> dict[str, object]:
    """Verifica conectividade com Qdrant. Retorna 503 se dependência crítica falhar."""
    checks: dict[str, str] = {}

    # Qdrant — dependência crítica para RAG
    try:
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=5.0,
        )
        client.get_collections()
        checks["qdrant"] = "ok"
    except (UnexpectedResponse, ConnectionError, OSError) as exc:
        logger.error("health_qdrant_failed", error=str(exc))
        checks["qdrant"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
        status_code=status_code,
    )

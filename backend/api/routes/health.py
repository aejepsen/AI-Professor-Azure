"""Endpoints de health check separados por responsabilidade.

/health/live  — liveness: processo está vivo? (sem I/O externo)
/health/ready — readiness: dependências alcançáveis? (Qdrant)
/health       — alias de /health/ready (compatibilidade)
"""
import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from backend.core.config import settings

logger = structlog.get_logger()
router = APIRouter()

# Cliente Qdrant reutilizável — não instanciar a cada probe
_qdrant_client: QdrantClient | None = None


def _get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=5.0,
        )
    return _qdrant_client


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Liveness probe — apenas verifica que o processo está respondendo."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    """Readiness probe — verifica conectividade com Qdrant."""
    checks: dict[str, str] = {}
    try:
        _get_qdrant_client().get_collections()
        checks["qdrant"] = "ok"
    except (UnexpectedResponse, ConnectionError, OSError, Exception) as exc:
        logger.error("health_qdrant_failed", error=str(exc))
        checks["qdrant"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )


@router.get("/health")
async def health() -> JSONResponse:
    """Alias de /health/ready para compatibilidade com health check do CD."""
    return await readiness()

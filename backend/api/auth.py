"""Middleware de autenticação JWT para Azure Entra ID."""
import hmac
import time
from typing import Any

import httpx
import structlog
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.core.config import settings

logger = structlog.get_logger()

_bearer_scheme = HTTPBearer()

_jwks_cache: dict[str, Any] | None = None
_jwks_cache_time: float = 0.0
_JWKS_TTL_SECONDS = 3600  # Revalida chaves a cada 1 hora


async def _get_jwks() -> Any:
    global _jwks_cache, _jwks_cache_time
    now = time.monotonic()
    if _jwks_cache is not None and (now - _jwks_cache_time) < _JWKS_TTL_SECONDS:
        return _jwks_cache
    url = (
        f"https://login.microsoftonline.com/"
        f"{settings.azure_tenant_id}/discovery/v2.0/keys"
    )
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_cache_time = now
    return _jwks_cache


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_scheme),
) -> dict[str, Any]:
    """
    Valida JWT do Azure Entra ID.

    Aceita também o token RAGAS fixo para endpoints de avaliação (/eval/*).

    Raises:
        HTTPException 401: token inválido, expirado ou com claims incorretos.
    """
    token = credentials.credentials

    # Token fixo para o pipeline RAGAS (CI/CD) — comparação constant-time
    if hmac.compare_digest(token, settings.ragas_test_token):
        logger.info("ragas_token_accepted")
        return {"sub": "ragas-ci", "roles": ["eval"]}

    try:
        unverified = jwt.get_unverified_claims(token)
        expected_aud = settings.azure_client_id
        logger.info("jwt_claims_preview", aud=unverified.get("aud"), iss=unverified.get("iss"), expected_aud=expected_aud, match=unverified.get("aud") == expected_aud)
        jwks = await _get_jwks()
        claims: dict[str, Any] = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.azure_client_id,
            issuer=f"https://login.microsoftonline.com/{settings.azure_tenant_id}/v2.0",
        )
        logger.info("jwt_validated", sub=claims.get("sub"))
        return claims
    except JWTError as exc:
        logger.warning("jwt_invalid", error=str(exc))
        raise HTTPException(status_code=401, detail=str(exc)) from exc

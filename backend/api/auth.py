"""Middleware de autenticação JWT para Azure Entra ID."""
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


async def _get_jwks() -> Any:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    url = (
        f"https://login.microsoftonline.com/"
        f"{settings.azure_tenant_id}/discovery/v2.0/keys"
    )
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        _jwks_cache = response.json()
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

    # Token fixo para o pipeline RAGAS (CI/CD)
    if token == settings.ragas_test_token:
        logger.info("ragas_token_accepted")
        return {"sub": "ragas-ci", "roles": ["eval"]}

    try:
        unverified = jwt.get_unverified_claims(token)
        logger.info("jwt_claims_preview", aud=unverified.get("aud"), iss=unverified.get("iss"))
        jwks = await _get_jwks()
        claims: dict[str, Any] = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=f"api://{settings.azure_client_id}",
            issuer=f"https://login.microsoftonline.com/{settings.azure_tenant_id}/v2.0",
        )
        logger.info("jwt_validated", sub=claims.get("sub"))
        return claims
    except JWTError as exc:
        logger.warning("jwt_invalid", error=str(exc))
        raise HTTPException(status_code=401, detail=str(exc)) from exc

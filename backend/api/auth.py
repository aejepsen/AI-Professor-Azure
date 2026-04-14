"""Middleware de autenticação JWT para Azure Entra ID."""
import asyncio
import hmac
import time
from typing import Any

import httpx
import structlog
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import DecodeError, ExpiredSignatureError, InvalidAudienceError
from jwt import InvalidIssuerError, InvalidTokenError
from jwt import decode as jwt_decode
from jwt.algorithms import RSAAlgorithm

from backend.core.config import settings

logger = structlog.get_logger()

_bearer_scheme = HTTPBearer()

_jwks_cache: dict[str, Any] | None = None
_jwks_cache_time: float = 0.0
_JWKS_TTL_SECONDS = 3600
_jwks_lock = asyncio.Lock()


async def _get_jwks() -> dict[str, Any]:
    global _jwks_cache, _jwks_cache_time
    now = time.monotonic()
    # Fast path: cache válido sem adquirir lock
    if _jwks_cache is not None and (now - _jwks_cache_time) < _JWKS_TTL_SECONDS:
        return _jwks_cache
    async with _jwks_lock:
        # Double-check após adquirir o lock — outra coroutine pode ter preenchido
        now = time.monotonic()
        if _jwks_cache is not None and (now - _jwks_cache_time) < _JWKS_TTL_SECONDS:
            return _jwks_cache
        url = (
            f"https://login.microsoftonline.com/"
            f"{settings.azure_tenant_id}/discovery/v2.0/keys"
        )
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=30.0)
                    response.raise_for_status()
                    _jwks_cache = response.json()
                    _jwks_cache_time = now
                    return _jwks_cache
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
        raise HTTPException(
            status_code=503, detail="Serviço de autenticação indisponível."
        ) from last_exc


def _find_public_key(jwks: dict[str, Any], token: str) -> Any:
    """Seleciona a chave pública correta do JWKS pelo kid do header do token."""
    import base64
    import json as _json

    try:
        header_part = token.split(".")[0]
        padding = 4 - len(header_part) % 4
        header = _json.loads(base64.urlsafe_b64decode(header_part + "=" * padding))
        kid = header.get("kid")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido.")

    keys = jwks.get("keys", [jwks]) if isinstance(jwks, dict) and "keys" in jwks else [jwks]

    for key_data in keys:
        if isinstance(key_data, dict) and (kid is None or key_data.get("kid") == kid):
            return RSAAlgorithm.from_jwk(key_data)

    # Fallback: usa primeira chave RSA disponível
    for key_data in keys:
        if isinstance(key_data, dict) and key_data.get("kty") == "RSA":
            return RSAAlgorithm.from_jwk(key_data)

    raise HTTPException(status_code=401, detail="Chave pública não encontrada no JWKS.")


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
        jwks = await _get_jwks()
        public_key = _find_public_key(jwks, token)
        claims: dict[str, Any] = jwt_decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.azure_client_id,
            issuer=f"https://login.microsoftonline.com/{settings.azure_tenant_id}/v2.0",
        )
        logger.info("jwt_validated", sub=claims.get("sub"))
        return claims
    except ExpiredSignatureError as exc:
        logger.warning("jwt_expired", error=str(exc))
        raise HTTPException(status_code=401, detail="Token expirado.") from exc
    except InvalidAudienceError as exc:
        logger.warning("jwt_invalid_audience", error=str(exc))
        raise HTTPException(status_code=401, detail="Invalid audience.") from exc
    except InvalidIssuerError as exc:
        logger.warning("jwt_invalid_issuer", error=str(exc))
        raise HTTPException(status_code=401, detail="Invalid issuer.") from exc
    except (InvalidTokenError, DecodeError) as exc:
        logger.warning("jwt_invalid", error=str(exc))
        raise HTTPException(status_code=401, detail=str(exc)) from exc


async def require_human_user(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Rejeita tokens de serviço/CI (role eval) em endpoints de uso humano."""
    if "eval" in user.get("roles", []):
        raise HTTPException(
            status_code=403,
            detail="Token de avaliação não autorizado neste endpoint.",
        )
    return user

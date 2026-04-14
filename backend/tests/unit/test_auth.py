"""Testes unitários para o middleware de autenticação JWT.

Usa par RSA real gerado em tempo de execução — os tokens são assinados com
RS256 (mesmo algoritmo do Azure Entra ID) e o mock de _get_jwks retorna JWKS
com a chave pública. Assim cada teste falha pelo motivo correto, não por
incompatibilidade de algoritmo.
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt.algorithms import RSAAlgorithm

TENANT_ID = "test-tenant-id"
CLIENT_ID = "test-client-id"
RAGAS_TOKEN = "test-ragas-token"

# Par RSA gerado uma vez por sessão de testes — suficientemente rápido (2048 bits)
_RSA_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

PRIVATE_KEY_PEM: str = _RSA_PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode()

# JWKS com a chave pública para uso nos mocks
_PUBLIC_JWK = json.loads(RSAAlgorithm.to_jwk(_RSA_PRIVATE_KEY.public_key()))
_PUBLIC_JWK["kid"] = "test-key-id"
_PUBLIC_JWK["use"] = "sig"
JWKS_RESPONSE: dict = {"keys": [_PUBLIC_JWK]}

# Segundo par para simular assinatura com chave errada
_RSA_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_PRIVATE_KEY_PEM: str = _RSA_OTHER_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode()


def _make_token(
    audience: str = CLIENT_ID,
    issuer: str = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
    expired: bool = False,
    private_key: str = PRIVATE_KEY_PEM,
    kid: str = "test-key-id",
) -> str:
    """Cria JWT RS256 assinado com a chave privada fornecida."""
    now = datetime.now(tz=timezone.utc)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    payload = {
        "aud": audience,
        "iss": issuer,
        "sub": "user-id-123",
        "exp": exp,
        "iat": now,
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture()
def mock_settings():
    with patch("backend.api.auth.settings") as s:
        s.azure_tenant_id = TENANT_ID
        s.azure_client_id = CLIENT_ID
        s.ragas_test_token = RAGAS_TOKEN
        yield s


@pytest.fixture()
def mock_jwks(mock_settings):
    """Mocka _get_jwks para retornar JWKS com a chave pública do par de teste."""
    with patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as m:
        m.return_value = JWKS_RESPONSE
        yield m


@pytest.mark.asyncio
async def test_valid_jwt_passes(mock_jwks):
    """Token RS256 válido (audience, issuer, exp corretos) deve retornar claims."""
    token = _make_token()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    from backend.api.auth import get_current_user

    claims = await get_current_user(credentials)
    assert claims["sub"] == "user-id-123"


@pytest.mark.asyncio
async def test_expired_jwt_returns_401(mock_jwks):
    """Token expirado deve retornar 401 — motivo: Token expirado."""
    token = _make_token(expired=True)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    from backend.api.auth import get_current_user

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)
    assert exc_info.value.status_code == 401
    assert "expirado" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_wrong_audience_returns_401(mock_jwks):
    """Audience incorreto deve retornar 401 — motivo: Invalid audience."""
    token = _make_token(audience="00000003-0000-0000-c000-000000000000")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    from backend.api.auth import get_current_user

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)
    assert exc_info.value.status_code == 401
    assert "audience" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_wrong_issuer_returns_401(mock_jwks):
    """Issuer incorreto deve retornar 401 — motivo: Invalid issuer."""
    token = _make_token(issuer="https://accounts.google.com")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    from backend.api.auth import get_current_user

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)
    assert exc_info.value.status_code == 401
    assert "issuer" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_invalid_signature_returns_401(mock_jwks):
    """Token assinado com chave RSA diferente deve retornar 401."""
    token = _make_token(private_key=OTHER_PRIVATE_KEY_PEM)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    from backend.api.auth import get_current_user

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_ragas_token_passes(mock_settings):
    """Token RAGAS fixo deve ser aceito sem validação JWT."""
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=RAGAS_TOKEN
    )

    from backend.api.auth import get_current_user

    claims = await get_current_user(credentials)
    assert claims["sub"] == "ragas-ci"


# ---------------------------------------------------------------------------
# Testes para _get_jwks — busca HTTP + cache
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_jwks_faz_requisicao_http_quando_cache_vazio(mock_settings):
    """Primeira chamada deve buscar as chaves na Microsoft via HTTP."""
    import backend.api.auth as auth_module

    fake_jwks = {"keys": [{"kty": "RSA", "kid": "abc123"}]}

    mock_response = MagicMock()
    mock_response.json.return_value = fake_jwks
    mock_response.raise_for_status = MagicMock()

    mock_http_client = AsyncMock()
    mock_http_client.get.return_value = mock_response
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    auth_module._jwks_cache = None  # garantir cache vazio

    with patch("backend.api.auth.httpx.AsyncClient", return_value=mock_http_client):
        result = await auth_module._get_jwks()

    assert result == fake_jwks
    expected_url = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
    mock_http_client.get.assert_called_once_with(expected_url, timeout=30.0)


@pytest.mark.asyncio
async def test_get_jwks_usa_cache_na_segunda_chamada(mock_settings):
    """Segunda chamada deve retornar do cache sem fazer nova requisição HTTP."""
    import backend.api.auth as auth_module

    cached_jwks = {"keys": [{"kty": "RSA", "kid": "cached"}]}
    auth_module._jwks_cache = cached_jwks

    with patch("backend.api.auth.httpx.AsyncClient") as mock_client_cls:
        result = await auth_module._get_jwks()

    assert result == cached_jwks
    mock_client_cls.assert_not_called()

    auth_module._jwks_cache = None  # limpar após o teste


@pytest.mark.asyncio
async def test_get_jwks_retorna_503_apos_tres_tentativas(mock_settings):
    """Após 3 tentativas com timeout, deve retornar HTTPException 503."""
    import backend.api.auth as auth_module
    import httpx
    from fastapi import HTTPException

    auth_module._jwks_cache = None

    mock_http_client = AsyncMock()
    mock_http_client.get.side_effect = httpx.TimeoutException("timeout")
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.api.auth.httpx.AsyncClient", return_value=mock_http_client):
        with patch("backend.api.auth.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await auth_module._get_jwks()

    assert exc_info.value.status_code == 503
    assert mock_http_client.get.call_count == 3  # exatamente 3 tentativas

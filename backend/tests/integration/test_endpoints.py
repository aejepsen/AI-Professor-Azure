"""Testes de integração para os endpoints da API.

Conforme especificado no Execution Plan §2.1.6:
  - POST /chat/stream com JWT válido retorna SSE 200
  - POST /chat/stream sem JWT retorna 401
  - POST /chat/stream com JWT de audiência errada retorna 401
  - GET  /health retorna {"status": "ok"}
  - GET  /eval/search com RAGAS token retorna resultados
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt
from datetime import datetime, timedelta, timezone

TENANT_ID = "test-tenant"
CLIENT_ID = "test-client"
RAGAS_TOKEN = "test-ragas-token"

# Par RSA real para testes de JWT válido (RS256 — mesmo algoritmo do Azure)
_RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_KEY_PEM = _RSA_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
_PUBLIC_KEY_PEM = _RSA_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()


def _make_valid_token(audience: str = f"api://{CLIENT_ID}/access_as_user") -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "aud": audience,
        "iss": f"https://sts.windows.net/{TENANT_ID}/",
        "sub": "user-integration-test",
        "exp": now + timedelta(hours=1),
        "iat": now,
    }
    return jose_jwt.encode(payload, _PRIVATE_KEY_PEM, algorithm="RS256")


@pytest.fixture(autouse=True)
def mock_settings_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.setenv("QDRANT_URL", "http://fake-qdrant")
    monkeypatch.setenv("QDRANT_API_KEY", "fake-qdrant-key")
    monkeypatch.setenv("AZURE_TENANT_ID", TENANT_ID)
    monkeypatch.setenv("AZURE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("RAGAS_TEST_TOKEN", RAGAS_TOKEN)


@pytest.fixture()
def client():
    with (
        patch("backend.services.knowledge_service.QdrantClient"),
        patch("backend.services.chat_service.anthropic.Anthropic"),
        patch("backend.agents.rag_agent.build_rag_graph"),
    ):
        from backend.api.main import app
        return TestClient(app)


def test_health_returns_ok(client):
    """GET /health deve retornar 200 com status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_stream_without_token_returns_401(client):
    """POST /chat/stream sem token deve retornar 401."""
    response = client.post("/chat/stream", json={"query": "test"})
    assert response.status_code == 403  # FastAPI retorna 403 quando Bearer ausente


def test_chat_stream_with_invalid_token_returns_401(client):
    """POST /chat/stream com token inválido deve retornar 401."""
    from jose import JWTError

    with patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks:
        mock_jwks.return_value = "fake-key"
        with patch("backend.api.auth.jwt.decode", side_effect=JWTError("invalid token")):
            response = client.post(
                "/chat/stream",
                json={"query": "test"},
                headers={"Authorization": "Bearer token-invalido"},
            )
    assert response.status_code == 401


def test_eval_search_with_ragas_token_returns_200(client):
    """GET /eval/search com token RAGAS deve retornar 200."""
    with patch("backend.api.routes.chat._knowledge_service") as mock_ks:
        mock_ks.search.return_value = []
        response = client.get(
            "/eval/search",
            params={"query": "férias"},
            headers={"Authorization": f"Bearer {RAGAS_TOKEN}"},
        )
    assert response.status_code == 200
    assert "results" in response.json()


def test_chat_stream_with_valid_jwt_returns_sse_200(client):
    """POST /chat/stream com JWT válido deve retornar 200 com Content-Type SSE."""
    token = _make_valid_token()

    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {
        "response_chunks": ["Você tem ", "30 dias ", "de férias."],
        "context": [],
        "error": None,
    }

    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
        patch("backend.api.routes.chat._rag_graph", fake_graph),
    ):
        mock_jwks.return_value = _PUBLIC_KEY_PEM
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.post(
            "/chat/stream",
            json={"query": "Quantos dias de férias tenho?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "30 dias" in response.text


def test_chat_stream_with_wrong_audience_returns_401(client):
    """POST /chat/stream com audience errado deve retornar 401 (não 200)."""
    token = _make_valid_token(audience="00000003-0000-0000-c000-000000000000")

    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
    ):
        mock_jwks.return_value = _PUBLIC_KEY_PEM
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.post(
            "/chat/stream",
            json={"query": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401

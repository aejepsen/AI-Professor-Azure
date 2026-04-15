"""Testes de integração para os endpoints da API.

Conforme especificado no Execution Plan §2.1.6:
  - POST /chat/stream com JWT válido retorna SSE 200
  - POST /chat/stream sem JWT retorna 401
  - POST /chat/stream com JWT de audiência errada retorna 401
  - GET  /health retorna {"status": "ok"}
  - GET  /eval/search com RAGAS token retorna resultados
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from slowapi.extension import Limiter
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

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

# JWKS com a chave pública para uso nos mocks de _get_jwks
_PUBLIC_JWK = json.loads(RSAAlgorithm.to_jwk(_RSA_KEY.public_key()))
_PUBLIC_JWK["kid"] = "test-key-id"
_PUBLIC_JWK["use"] = "sig"
JWKS_RESPONSE = {"keys": [_PUBLIC_JWK]}


def _make_valid_token(audience: str = CLIENT_ID) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "aud": audience,
        "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        "sub": "user-integration-test",
        "exp": now + timedelta(hours=1),
        "iat": now,
    }
    return jwt.encode(payload, _PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "test-key-id"})


@pytest.fixture(autouse=True)
def disable_rate_limits():
    """Desabilita rate limiting para isolar testes de ordem e contagem de requests.

    _check_request_limit é substituído por uma corotina que seta view_rate_limit=None.
    _inject_headers checa `if current_limit:` e, com None, pula a injeção de headers
    sem precisar modificar _headers_enabled nem lançar AttributeError.
    """
    def _noop_check(self, request, endpoint, deduct):  # noqa: ANN001
        request.state.view_rate_limit = None

    with patch.object(Limiter, "_check_request_limit", _noop_check):
        yield


@pytest.fixture(autouse=True)
def mock_settings_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.setenv("QDRANT_URL", "http://fake-qdrant")
    monkeypatch.setenv("QDRANT_API_KEY", "fake-qdrant-key")
    monkeypatch.setenv("AZURE_TENANT_ID", TENANT_ID)
    monkeypatch.setenv("AZURE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("RAGAS_TEST_TOKEN", RAGAS_TOKEN)
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "fake-assemblyai-key")
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_NAME", "fake-storage")
    monkeypatch.setenv("AZURE_STORAGE_ACCOUNT_KEY", "ZmFrZWtleWZha2VrZXlmYWtla2V5ZmFrZWtleWZha2VrZXlmYWtla2V5ZmFrZWtleWZha2VrZXlmYWtla2V5Zg==")
    monkeypatch.setenv("AZURE_STORAGE_CONTAINER", "uploads")


@pytest.fixture()
def client():
    with (
        patch("backend.services.knowledge_service.QdrantClient"),
        patch("backend.services.knowledge_service.get_dense_model"),
        patch("backend.services.knowledge_service.get_sparse_model"),
        patch("backend.services.ingest_service.QdrantClient"),
        patch("backend.services.ingest_service.get_dense_model"),
        patch("backend.services.ingest_service.get_sparse_model"),
        patch("backend.services.chat_service.anthropic.Anthropic"),
        patch("backend.agents.rag_agent.build_rag_graph"),
        patch("backend.services.blob_service.BlobServiceClient"),
    ):
        from backend.api.main import app
        return TestClient(app)


def test_health_returns_ok(client):
    """GET /health deve retornar 200 com Qdrant respondendo."""
    mock_qdrant = MagicMock()
    mock_qdrant.get_collections.return_value = MagicMock()
    with patch("backend.api.routes.health.QdrantClient", return_value=mock_qdrant):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"]["qdrant"] == "ok"


def test_health_returns_503_when_qdrant_down(client):
    """GET /health deve retornar 503 quando Qdrant está indisponível."""
    mock_qdrant = MagicMock()
    mock_qdrant.get_collections.side_effect = ConnectionError("Connection refused")
    with patch("backend.api.routes.health.QdrantClient", return_value=mock_qdrant):
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["qdrant"] == "error"


def test_chat_stream_without_token_returns_401(client):
    """POST /chat/stream sem token deve retornar 401."""
    response = client.post("/chat/stream", json={"query": "test"})
    assert response.status_code == 401


def test_chat_stream_with_invalid_token_returns_401(client):
    """POST /chat/stream com token inválido deve retornar 401."""
    from jwt import InvalidTokenError

    with patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks:
        mock_jwks.return_value = JWKS_RESPONSE
        with patch("backend.api.auth.jwt_decode", side_effect=InvalidTokenError("invalid token")):
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
        mock_jwks.return_value = JWKS_RESPONSE
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


def test_ingest_without_token_returns_401(client):
    """POST /ingest sem token deve retornar 401."""
    response = client.post("/ingest", files={"file": ("aula.mp3", b"fake", "audio/mpeg")})
    assert response.status_code == 401


def test_ingest_unsupported_format_returns_400(client):
    """POST /ingest com formato não suportado deve retornar 400."""
    token = _make_valid_token()
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.post(
            "/ingest",
            files={"file": ("aula.pdf", b"fake-pdf", "application/pdf")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 400
    assert "não suportado" in response.json()["detail"]


def test_ingest_valid_file_returns_200(client):
    """POST /ingest com arquivo válido deve retornar 200 com n_chunks."""
    token = _make_valid_token()
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
        patch("backend.api.routes.ingest._ingest_service") as mock_ingest,
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        mock_ingest.ingest.return_value = {
            "filename": "aula.mp3",
            "n_chunks": 12,
            "duration_sec": 3600.0,
        }
        # b"\xff\xfb" = MP3 frame sync (magic bytes válidos)
        response = client.post(
            "/ingest",
            files={"file": ("aula.mp3", b"\xff\xfb" + b"\x00" * 10, "audio/mpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["n_chunks"] == 12
    assert response.json()["status"] == "ok"


def test_ingest_arquivo_grande_retorna_413(client):
    """POST /ingest com arquivo acima do limite deve retornar 413."""
    token = _make_valid_token()
    big_file = b"x" * (1025 * 1024 * 1024)  # > 1024 MB

    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.post(
            "/ingest",
            files={"file": ("aula.mp3", big_file, "audio/mpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 413


def test_ingest_service_error_retorna_500(client):
    """POST /ingest com erro no IngestService deve retornar 500 com mensagem genérica."""
    token = _make_valid_token()
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
        patch("backend.api.routes.ingest._ingest_service") as mock_ingest,
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        mock_ingest.ingest.side_effect = RuntimeError("AssemblyAI falhou")
        response = client.post(
            "/ingest",
            files={"file": ("aula.mp3", b"\xff\xfb" + b"\x00" * 10, "audio/mpeg")},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "Erro ao processar arquivo."


def test_get_sas_token_formato_invalido_retorna_400(client):
    """GET /ingest/sas-token com extensão não suportada deve retornar 400."""
    token = _make_valid_token()
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.get(
            "/ingest/sas-token",
            params={"filename": "documento.pdf"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 400


def test_get_sas_token_sucesso_retorna_url_e_blob_name(client):
    """GET /ingest/sas-token com arquivo válido deve retornar upload_url e blob_name."""
    token = _make_valid_token()
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
        patch("backend.api.routes.ingest._blob_service") as mock_blob,
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        mock_blob.generate_upload_sas.return_value = ("https://sas.url/video.mp4", "uuid/video.mp4")
        response = client.get(
            "/ingest/sas-token",
            params={"filename": "video.mp4"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["upload_url"] == "https://sas.url/video.mp4"
    assert response.json()["blob_name"] == "uuid/video.mp4"


def test_get_sas_token_erro_no_servico_retorna_500(client):
    """GET /ingest/sas-token com erro no BlobService deve retornar 500 com mensagem genérica."""
    token = _make_valid_token()
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
        patch("backend.api.routes.ingest._blob_service") as mock_blob,
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        mock_blob.generate_upload_sas.side_effect = Exception("Azure error")
        response = client.get(
            "/ingest/sas-token",
            params={"filename": "video.mp4"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 500
    assert response.json()["detail"] == "Erro ao gerar URL de upload."


def test_process_blob_cria_job_e_retorna_job_id(client):
    """POST /ingest/process deve criar job e retornar job_id imediatamente."""
    token = _make_valid_token()
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
        patch("backend.api.routes.ingest._blob_service"),
        patch("backend.api.routes.ingest._ingest_service"),
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.post(
            "/ingest/process",
            json={"blob_name": "uuid/video.mp4", "original_filename": "video.mp4"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "job_id" in body
    assert body["status"] == "processing"


def test_process_blob_blob_name_path_traversal_retorna_422(client):
    """POST /ingest/process com blob_name contendo '..' deve retornar 422."""
    token = _make_valid_token()
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.post(
            "/ingest/process",
            json={"blob_name": "../other-container/secret.mp4", "original_filename": "video.mp4"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 422


def test_get_job_status_nao_encontrado_retorna_404(client):
    """GET /ingest/status/{job_id} com ID inexistente deve retornar 404."""
    token = _make_valid_token()
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.get(
            "/ingest/status/id-que-nao-existe",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 404


def test_get_job_status_processing(client):
    """GET /ingest/status deve retornar 'processing' para job em andamento."""
    import backend.api.routes.ingest as ingest_module

    token = _make_valid_token()
    job_id = "job-em-andamento"
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
        patch.dict(ingest_module._jobs, {job_id: {"status": "processing"}}),
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.get(
            f"/ingest/status/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "processing"


def test_get_job_status_done(client):
    """GET /ingest/status deve retornar resultado completo para job concluído."""
    import backend.api.routes.ingest as ingest_module

    token = _make_valid_token()
    job_id = "job-concluido"
    done_job = {
        "status": "done",
        "result": {"filename": "aula.mp3", "n_chunks": 8, "duration_sec": 600.0},
    }
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
        patch.dict(ingest_module._jobs, {job_id: done_job}),
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.get(
            f"/ingest/status/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["n_chunks"] == 8
    assert body["filename"] == "aula.mp3"


def test_get_job_status_error(client):
    """GET /ingest/status deve retornar 500 para job com erro."""
    import backend.api.routes.ingest as ingest_module

    token = _make_valid_token()
    job_id = "job-com-erro"
    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
        patch.dict(ingest_module._jobs, {job_id: {"status": "error", "error": "Falhou"}}),
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.get(
            f"/ingest/status/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 500


def test_run_ingest_sucesso_atualiza_job_para_done():
    """_run_ingest bem-sucedido deve marcar job como done com resultado."""
    import backend.api.routes.ingest as ingest_module

    test_jobs = {"job-1": {"status": "processing"}}
    mock_blob = MagicMock()
    mock_blob.get_read_url.return_value = "https://sas.url"
    mock_blob.delete_blob.return_value = None
    mock_ingest = MagicMock()
    mock_ingest.ingest_from_url.return_value = {
        "filename": "video.mp4", "n_chunks": 5, "duration_sec": 300.0
    }

    with (
        patch.object(ingest_module, "_jobs", test_jobs),
        patch.object(ingest_module, "_blob_service", mock_blob),
        patch.object(ingest_module, "_ingest_service", mock_ingest),
    ):
        ingest_module._run_ingest("job-1", "uuid/video.mp4", "video.mp4")

    assert test_jobs["job-1"]["status"] == "done"
    assert test_jobs["job-1"]["result"]["n_chunks"] == 5
    mock_blob.delete_blob.assert_called_once_with("uuid/video.mp4")


def test_run_ingest_erro_atualiza_job_para_error():
    """_run_ingest com falha deve marcar job como error e sempre deletar o blob."""
    import backend.api.routes.ingest as ingest_module

    test_jobs = {"job-2": {"status": "processing"}}
    mock_blob = MagicMock()
    mock_blob.get_read_url.side_effect = Exception("Blob inacessível")
    mock_ingest = MagicMock()

    with (
        patch.object(ingest_module, "_jobs", test_jobs),
        patch.object(ingest_module, "_blob_service", mock_blob),
        patch.object(ingest_module, "_ingest_service", mock_ingest),
    ):
        ingest_module._run_ingest("job-2", "uuid/video.mp4", "video.mp4")

    assert test_jobs["job-2"]["status"] == "error"
    mock_blob.delete_blob.assert_called_once_with("uuid/video.mp4")


def test_chat_stream_with_wrong_audience_returns_401(client):
    """POST /chat/stream com audience errado deve retornar 401 (não 200)."""
    token = _make_valid_token(audience="00000003-0000-0000-c000-000000000000")

    with (
        patch("backend.api.auth._get_jwks", new_callable=AsyncMock) as mock_jwks,
        patch("backend.api.auth.settings") as mock_auth_settings,
    ):
        mock_jwks.return_value = JWKS_RESPONSE
        mock_auth_settings.azure_client_id = CLIENT_ID
        mock_auth_settings.azure_tenant_id = TENANT_ID
        mock_auth_settings.ragas_test_token = RAGAS_TOKEN
        response = client.post(
            "/chat/stream",
            json={"query": "test"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401


def test_chat_stream_com_ragas_token_retorna_403(client):
    """POST /chat/stream com token RAGAS (role=eval) deve retornar 403.

    Garante que require_human_user bloqueia tokens de CI/eval em endpoints
    de uso humano — vetor de escalonamento de privilégio.
    """
    response = client.post(
        "/chat/stream",
        json={"query": "test"},
        headers={"Authorization": f"Bearer {RAGAS_TOKEN}"},
    )
    assert response.status_code == 403
    assert "avaliação" in response.json()["detail"].lower()


def test_ingest_com_ragas_token_retorna_403(client):
    """POST /ingest com token RAGAS (role=eval) deve retornar 403."""
    response = client.post(
        "/ingest",
        files={"file": ("aula.mp3", b"fake", "audio/mpeg")},
        headers={"Authorization": f"Bearer {RAGAS_TOKEN}"},
    )
    assert response.status_code == 403

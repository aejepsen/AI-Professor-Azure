"""Testes do contêiner Docker.

Verifica que a imagem construída:
  - Inicia sem erro de importação (Dockerfile correto)
  - Responde /health com {"status": "ok"}
  - Rejeita /chat/stream sem token (401/403)
  - Aceita RAGAS token em /eval/search (200)

Requer Docker disponível. Rodar com:
  pytest tests/docker/ -v -m docker

Este teste deve ser executado ANTES de qualquer push para ghcr.io.
"""
import pathlib
import subprocess
import time
import uuid

import pytest
import requests

BACKEND_DIR = pathlib.Path(__file__).parent.parent.parent.resolve()
IMAGE_TAG = f"ai-professor-backend-test:{uuid.uuid4().hex[:8]}"
CONTAINER_NAME = f"ai-professor-test-{uuid.uuid4().hex[:8]}"
PORT = 18000


@pytest.fixture(scope="module")
def docker_container():
    """Build da imagem e run do container. Teardown garante limpeza."""
    build = subprocess.run(
        ["docker", "build", "-t", IMAGE_TAG, str(BACKEND_DIR)],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, f"docker build falhou:\n{build.stderr}"

    run = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", CONTAINER_NAME,
            "-p", f"{PORT}:8000",
            "-e", "ANTHROPIC_API_KEY=sk-ant-fake-key-for-test",
            "-e", "QDRANT_URL=http://fake-qdrant:6333",
            "-e", "QDRANT_API_KEY=fake-key",
            "-e", "AZURE_TENANT_ID=test-tenant",
            "-e", "AZURE_CLIENT_ID=test-client",
            "-e", "RAGAS_TEST_TOKEN=test-ragas-token",
            "-e", "ASSEMBLYAI_API_KEY=fake-assemblyai-key",
            IMAGE_TAG,
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, f"docker run falhou:\n{run.stderr}"

    # Aguarda app iniciar (máx 20s)
    base_url = f"http://localhost:{PORT}"
    started = False
    for _ in range(20):
        try:
            r = requests.get(f"{base_url}/health", timeout=1)
            if r.status_code == 200:
                started = True
                break
        except requests.exceptions.ConnectionError:
            time.sleep(1)

    if not started:
        logs = subprocess.run(
            ["docker", "logs", CONTAINER_NAME],
            capture_output=True,
            text=True,
        )
        subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True)
        subprocess.run(["docker", "rm", CONTAINER_NAME], capture_output=True)
        subprocess.run(["docker", "rmi", IMAGE_TAG], capture_output=True)
        pytest.fail(
            f"Container não iniciou em 20s.\nLogs:\n{logs.stdout}\n{logs.stderr}"
        )

    yield base_url

    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True)
    subprocess.run(["docker", "rm", CONTAINER_NAME], capture_output=True)
    subprocess.run(["docker", "rmi", IMAGE_TAG], capture_output=True)


@pytest.mark.docker
def test_container_starts_and_health_ok(docker_container):
    """/health retorna 200 — garante que não há ImportError no startup."""
    r = requests.get(f"{docker_container}/health", timeout=5)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.docker
def test_container_rejects_unauthenticated_chat(docker_container):
    """POST /chat/stream sem token retorna 401/403, não 500."""
    r = requests.post(
        f"{docker_container}/chat/stream",
        json={"query": "teste"},
        timeout=5,
    )
    assert r.status_code in (401, 403), (
        f"Esperado 401/403, recebido {r.status_code}. "
        "Verifique se o app iniciou corretamente."
    )


@pytest.mark.docker
def test_container_accepts_ragas_token(docker_container):
    """GET /eval/search com RAGAS token retorna 200."""
    r = requests.get(
        f"{docker_container}/eval/search",
        params={"query": "férias"},
        headers={"Authorization": "Bearer test-ragas-token"},
        timeout=10,
    )
    assert r.status_code == 200
    assert "results" in r.json()

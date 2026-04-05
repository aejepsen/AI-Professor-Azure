"""Testes unitários para o BlobService."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from backend.services.blob_service import BlobService


@pytest.fixture()
def service():
    with (
        patch("backend.services.blob_service.BlobServiceClient") as MockClient,
        patch("backend.services.blob_service.settings") as s,
    ):
        s.azure_storage_account_name = "testaccount"
        s.azure_storage_account_key = "dGVzdGtleQ=="
        s.azure_storage_container = "uploads"

        mock_client = MagicMock()
        MockClient.return_value = mock_client

        svc = BlobService()
        svc._mock_client = mock_client
        yield svc


# ---------------------------------------------------------------------------
# generate_upload_sas
# ---------------------------------------------------------------------------

def test_generate_upload_sas_retorna_url_e_blob_name(service):
    with patch("backend.services.blob_service.generate_blob_sas", return_value="sig=abc") as mock_sas:
        url, blob_name = service.generate_upload_sas("aula.mp4")

    assert "aula.mp4" in blob_name
    assert blob_name.count("/") == 1  # uuid/filename
    assert "testaccount.blob.core.windows.net" in url
    assert "sig=abc" in url


def test_generate_upload_sas_inclui_uuid_no_blob_name(service):
    with patch("backend.services.blob_service.generate_blob_sas", return_value="tok"):
        _, blob1 = service.generate_upload_sas("video.mkv")
        _, blob2 = service.generate_upload_sas("video.mkv")

    # UUIDs diferentes garantem nomes únicos
    assert blob1 != blob2


def test_generate_upload_sas_chama_generate_blob_sas_com_permissao_escrita(service):
    with patch("backend.services.blob_service.generate_blob_sas", return_value="t") as mock_sas, \
         patch("backend.services.blob_service.BlobSasPermissions") as MockPerm:
        MockPerm.return_value = MagicMock()
        service.generate_upload_sas("file.mp4")

    mock_sas.assert_called_once()
    call_kwargs = mock_sas.call_args[1]
    assert call_kwargs["account_name"] == "testaccount"
    assert call_kwargs["container_name"] == "uploads"


def test_generate_upload_sas_expiry_duas_horas(service):
    captured = {}

    def fake_sas(**kwargs):
        captured["expiry"] = kwargs["expiry"]
        return "token"

    with patch("backend.services.blob_service.generate_blob_sas", side_effect=fake_sas):
        service.generate_upload_sas("video.mp4")

    now = datetime.now(tz=timezone.utc)
    delta = captured["expiry"] - now
    assert 6900 < delta.total_seconds() < 7500  # ~2h


# ---------------------------------------------------------------------------
# get_read_url
# ---------------------------------------------------------------------------

def test_get_read_url_retorna_url_com_blob_name(service):
    with patch("backend.services.blob_service.generate_blob_sas", return_value="read_sig"):
        url = service.get_read_url("uuid/aula.mp4")

    assert "uuid/aula.mp4" in url
    assert "testaccount.blob.core.windows.net" in url
    assert "read_sig" in url


def test_get_read_url_expiry_quatro_horas(service):
    captured = {}

    def fake_sas(**kwargs):
        captured["expiry"] = kwargs["expiry"]
        return "t"

    with patch("backend.services.blob_service.generate_blob_sas", side_effect=fake_sas):
        service.get_read_url("blob/file.mkv")

    now = datetime.now(tz=timezone.utc)
    delta = captured["expiry"] - now
    assert 14100 < delta.total_seconds() < 14700  # ~4h


# ---------------------------------------------------------------------------
# delete_blob
# ---------------------------------------------------------------------------

def test_delete_blob_chama_delete_no_blob_client(service):
    mock_blob_client = MagicMock()
    service._client.get_blob_client.return_value = mock_blob_client

    service.delete_blob("uuid/aula.mp4")

    service._client.get_blob_client.assert_called_once_with(
        container="uploads", blob="uuid/aula.mp4"
    )
    mock_blob_client.delete_blob.assert_called_once()


def test_delete_blob_nao_levanta_excecao_em_falha(service):
    service._client.get_blob_client.side_effect = Exception("Storage unavailable")

    # Deve logar warning e não propagar
    service.delete_blob("uuid/aula.mp4")

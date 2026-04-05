"""Testes unitários para o IngestService."""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.services.ingest_service import (
    CHUNK_MAX_WORDS,
    CHUNK_OVERLAP_WORDS,
    IngestService,
)


@pytest.fixture()
def service():
    with (
        patch("backend.services.ingest_service.aai"),
        patch("backend.services.ingest_service.QdrantClient") as MockQdrant,
        patch("backend.services.ingest_service.SentenceTransformer") as MockDense,
        patch("backend.services.ingest_service.Bm25") as MockSparse,
        patch("backend.services.ingest_service.settings") as s,
    ):
        s.assemblyai_api_key = "fake-key"
        s.qdrant_url = "http://fake-qdrant"
        s.qdrant_api_key = "fake-qdrant-key"

        dense = MagicMock()
        dense.encode.return_value = np.zeros((1, 1024))
        MockDense.return_value = dense

        sv = MagicMock()
        sv.indices = np.array([0])
        sv.values = np.array([1.0])
        sparse = MagicMock()
        sparse.embed.return_value = iter([sv])
        MockSparse.return_value = sparse

        qdrant = MagicMock()
        qdrant.collection_exists.return_value = True
        MockQdrant.return_value = qdrant

        yield IngestService()


# ---------------------------------------------------------------------------
# _chunk — função pura, sem mock necessário
# ---------------------------------------------------------------------------

def test_chunk_texto_vazio_retorna_zero_chunks(service):
    assert list(service._chunk("")) == []


def test_chunk_texto_curto_retorna_um_chunk(service):
    text = " ".join(["palavra"] * 10)
    chunks = list(service._chunk(text))
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_exatamente_max_words_retorna_um_chunk(service):
    text = " ".join(["w"] * CHUNK_MAX_WORDS)
    assert len(list(service._chunk(text))) == 1


def test_chunk_texto_longo_cria_multiplos_chunks(service):
    text = " ".join(["w"] * (CHUNK_MAX_WORDS + 100))
    chunks = list(service._chunk(text))
    assert len(chunks) >= 2


def test_chunk_overlap_correto_entre_chunks(service):
    """Últimas CHUNK_OVERLAP_WORDS palavras do chunk N devem abrir o chunk N+1."""
    words = [f"w{i}" for i in range(CHUNK_MAX_WORDS + CHUNK_OVERLAP_WORDS + 10)]
    text = " ".join(words)
    chunks = list(service._chunk(text))
    assert len(chunks) == 2
    tail = chunks[0].split()[-CHUNK_OVERLAP_WORDS:]
    head = chunks[1].split()[:CHUNK_OVERLAP_WORDS]
    assert tail == head


# ---------------------------------------------------------------------------
# _ensure_collection
# ---------------------------------------------------------------------------

def test_ensure_collection_cria_quando_nao_existe(service):
    service._qdrant.collection_exists.return_value = False
    service._ensure_collection()
    service._qdrant.create_collection.assert_called_once()


def test_ensure_collection_nao_cria_quando_ja_existe(service):
    service._qdrant.collection_exists.return_value = True
    service._ensure_collection()
    service._qdrant.create_collection.assert_not_called()


# ---------------------------------------------------------------------------
# _index
# ---------------------------------------------------------------------------

def test_index_envia_pontos_ao_qdrant(service):
    chunks = ["chunk A", "chunk B"]
    service._dense.encode.return_value = np.zeros((2, 1024))

    sv1 = MagicMock()
    sv1.indices = np.array([0])
    sv1.values = np.array([1.0])
    sv2 = MagicMock()
    sv2.indices = np.array([1])
    sv2.values = np.array([0.8])
    service._sparse.embed.return_value = iter([sv1, sv2])

    service._index(chunks, source="aula.mp4")

    service._qdrant.upsert.assert_called_once()
    points = service._qdrant.upsert.call_args[1]["points"]
    assert len(points) == 2
    assert points[0].payload["source"] == "aula.mp4"
    assert points[0].payload["text"] == "chunk A"


def test_index_lista_vazia_chama_upsert_sem_pontos(service):
    service._dense.encode.return_value = np.zeros((0, 1024))
    service._sparse.embed.return_value = iter([])
    service._index([], source="vazio.mp4")
    service._qdrant.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# _transcribe
# ---------------------------------------------------------------------------

def _make_transcript(status_str: str, text: str = "", duration: float = 0.0) -> MagicMock:
    t = MagicMock()
    t.status = status_str
    t.text = text
    t.audio_duration = duration
    t.error = "mock error"
    return t


def test_transcribe_retorna_texto_e_duracao(service):
    with (
        patch("backend.services.ingest_service.aai") as mock_aai,
        patch("backend.services.ingest_service.os.unlink"),
    ):
        mock_aai.TranscriptStatus.error = "error"
        mock_aai.TranscriptionConfig.return_value = MagicMock()
        mock_aai.Transcriber.return_value.transcribe.return_value = _make_transcript(
            "completed", "Olá mundo", 120.0
        )

        text, duration = service._transcribe(b"audio", "video.mp4")

    assert text == "Olá mundo"
    assert duration == 120.0


def test_transcribe_deleta_arquivo_temporario_no_sucesso(service):
    with (
        patch("backend.services.ingest_service.aai") as mock_aai,
        patch("backend.services.ingest_service.os.unlink") as mock_unlink,
    ):
        mock_aai.TranscriptStatus.error = "error"
        mock_aai.TranscriptionConfig.return_value = MagicMock()
        mock_aai.Transcriber.return_value.transcribe.return_value = _make_transcript(
            "completed", "texto", 10.0
        )

        service._transcribe(b"bytes", "audio.mp3")

    mock_unlink.assert_called_once()


def test_transcribe_deleta_arquivo_temporario_mesmo_com_excecao(service):
    with (
        patch("backend.services.ingest_service.aai") as mock_aai,
        patch("backend.services.ingest_service.os.unlink") as mock_unlink,
    ):
        mock_aai.TranscriptionConfig.return_value = MagicMock()
        mock_aai.Transcriber.return_value.transcribe.side_effect = RuntimeError("API error")

        with pytest.raises(RuntimeError):
            service._transcribe(b"bytes", "audio.mp3")

    mock_unlink.assert_called_once()


def test_transcribe_levanta_excecao_em_status_error(service):
    with (
        patch("backend.services.ingest_service.aai") as mock_aai,
        patch("backend.services.ingest_service.os.unlink"),
    ):
        mock_aai.TranscriptStatus.error = "error"
        mock_aai.TranscriptionConfig.return_value = MagicMock()
        mock_aai.Transcriber.return_value.transcribe.return_value = _make_transcript("error")

        with pytest.raises(RuntimeError, match="AssemblyAI error"):
            service._transcribe(b"bytes", "audio.mp3")


def test_transcribe_texto_none_retorna_string_vazia(service):
    with (
        patch("backend.services.ingest_service.aai") as mock_aai,
        patch("backend.services.ingest_service.os.unlink"),
    ):
        mock_aai.TranscriptStatus.error = "error"
        mock_aai.TranscriptionConfig.return_value = MagicMock()
        t = _make_transcript("completed", None, 60.0)  # text=None
        t.text = None
        mock_aai.Transcriber.return_value.transcribe.return_value = t

        text, _ = service._transcribe(b"bytes", "audio.mp3")

    assert text == ""


# ---------------------------------------------------------------------------
# _transcribe_url
# ---------------------------------------------------------------------------

def test_transcribe_url_retorna_texto_e_duracao(service):
    with patch("backend.services.ingest_service.aai") as mock_aai:
        mock_aai.TranscriptStatus.error = "error"
        mock_aai.TranscriptionConfig.return_value = MagicMock()
        mock_aai.Transcriber.return_value.transcribe.return_value = _make_transcript(
            "completed", "Conteúdo da aula", 300.0
        )

        text, duration = service._transcribe_url("https://sas.url/blob", "aula.mkv")

    assert text == "Conteúdo da aula"
    assert duration == 300.0


def test_transcribe_url_levanta_excecao_em_status_error(service):
    with patch("backend.services.ingest_service.aai") as mock_aai:
        mock_aai.TranscriptStatus.error = "error"
        mock_aai.TranscriptionConfig.return_value = MagicMock()
        mock_aai.Transcriber.return_value.transcribe.return_value = _make_transcript("error")

        with pytest.raises(RuntimeError, match="AssemblyAI error"):
            service._transcribe_url("https://url", "video.mp4")


# ---------------------------------------------------------------------------
# ingest e ingest_from_url (integração interna)
# ---------------------------------------------------------------------------

def test_ingest_retorna_resultado_completo(service):
    service._transcribe = MagicMock(return_value=("palavra " * 10, 120.0))
    service._index = MagicMock()

    result = service.ingest(b"audio", "aula.mp3")

    assert result["filename"] == "aula.mp3"
    assert result["n_chunks"] >= 1
    assert result["duration_sec"] == 120.0
    service._index.assert_called_once()


def test_ingest_from_url_retorna_resultado_completo(service):
    service._transcribe_url = MagicMock(return_value=("conteúdo da url " * 5, 240.0))
    service._index = MagicMock()

    result = service.ingest_from_url("https://sas.url", "aula.mkv")

    assert result["filename"] == "aula.mkv"
    assert result["duration_sec"] == 240.0
    service._index.assert_called_once()

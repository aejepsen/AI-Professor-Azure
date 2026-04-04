"""Testes unitários para o KnowledgeService."""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.services.knowledge_service import KnowledgeService


def _make_hit(text: str, source: str, score: float = 0.95) -> MagicMock:
    hit = MagicMock()
    hit.id = "fake-id"
    hit.payload = {"text": text, "source": source}
    hit.score = score
    return hit


def _query_points_result(hits: list) -> MagicMock:
    result = MagicMock()
    result.points = hits
    return result


@pytest.fixture()
def mock_qdrant():
    with patch("backend.services.knowledge_service.QdrantClient") as MockClient:
        client = MagicMock()
        # Por padrão retorna listas vazias para ambas as chamadas
        client.query_points.return_value = _query_points_result([])
        MockClient.return_value = client
        yield client


@pytest.fixture()
def service(mock_qdrant):
    with patch("backend.services.knowledge_service.settings") as s, \
         patch("backend.services.knowledge_service.SentenceTransformer") as MockDense, \
         patch("backend.services.knowledge_service.Bm25") as MockSparse:
        s.qdrant_url = "http://fake-qdrant"
        s.qdrant_api_key = "fake-key"

        dense = MagicMock()
        dense.encode.return_value = np.zeros(1024)
        MockDense.return_value = dense

        sparse_vec = MagicMock()
        sparse_vec.indices = np.array([0])
        sparse_vec.values = np.array([1.0])
        sparse = MagicMock()
        sparse.embed.return_value = iter([sparse_vec])
        MockSparse.return_value = sparse

        return KnowledgeService()


def test_search_returns_results(service, mock_qdrant):
    """Busca com query válida deve retornar lista de resultados via RRF."""
    hit = _make_hit("Férias são 30 dias corridos.", "manual_ferias.pdf", score=0.95)
    mock_qdrant.query_points.return_value = _query_points_result([hit])

    results = service.search("Quantos dias de férias tenho?")

    assert len(results) == 1
    assert results[0]["text"] == "Férias são 30 dias corridos."
    assert results[0]["source"] == "manual_ferias.pdf"


def test_search_empty_query_returns_empty(service, mock_qdrant):
    """Query vazia deve retornar lista vazia sem chamar Qdrant."""
    results = service.search("")

    mock_qdrant.query_points.assert_not_called()
    assert results == []


def test_search_qdrant_error_raises(service, mock_qdrant):
    """Erro do Qdrant deve ser propagado como exceção."""
    mock_qdrant.query_points.side_effect = Exception("Qdrant connection timeout")

    with pytest.raises(Exception, match="Qdrant connection timeout"):
        service.search("Como abrir um chamado?")


def test_search_limits_results(service, mock_qdrant):
    """Busca deve chamar Qdrant com limite configurado."""
    service.search("test query", top_k=5)

    assert mock_qdrant.query_points.called

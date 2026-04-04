"""Testes unitários para o KnowledgeService."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.knowledge_service import KnowledgeService


@pytest.fixture()
def mock_qdrant():
    with patch("backend.services.knowledge_service.QdrantClient") as MockClient:
        client = MagicMock()
        MockClient.return_value = client
        yield client


@pytest.fixture()
def service(mock_qdrant):
    import numpy as np

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
    """Busca com query válida deve retornar lista de resultados."""
    mock_result = MagicMock()
    mock_result.payload = {"text": "Férias são 30 dias corridos.", "source": "manual_ferias.pdf"}
    mock_result.score = 0.95
    mock_qdrant.search.return_value = [mock_result]

    results = service.search("Quantos dias de férias tenho?")

    assert len(results) == 1
    assert results[0]["text"] == "Férias são 30 dias corridos."
    assert results[0]["score"] == 0.95


def test_search_empty_query_returns_empty(service, mock_qdrant):
    """Query vazia deve retornar lista vazia sem chamar Qdrant."""
    results = service.search("")

    mock_qdrant.search.assert_not_called()
    assert results == []


def test_search_qdrant_error_raises(service, mock_qdrant):
    """Erro do Qdrant deve ser propagado como exceção."""
    mock_qdrant.search.side_effect = Exception("Qdrant connection timeout")

    with pytest.raises(Exception, match="Qdrant connection timeout"):
        service.search("Como abrir um chamado?")


def test_search_limits_results(service, mock_qdrant):
    """Busca deve respeitar o limite de resultados configurado."""
    mock_qdrant.search.return_value = []

    service.search("test query", top_k=5)

    call_kwargs = mock_qdrant.search.call_args
    assert call_kwargs is not None

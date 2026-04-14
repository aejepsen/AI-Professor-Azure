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
    """Simula o objeto retornado por client.query_points() com atributo .points."""
    result = MagicMock()
    result.points = hits
    return result


@pytest.fixture()
def mock_qdrant():
    with patch("backend.services.knowledge_service.QdrantClient") as MockClient:
        client = MagicMock()
        # Por padrão retorna listas vazias para ambas as chamadas
        client.search.return_value = []
        MockClient.return_value = client
        yield client


@pytest.fixture()
def service(mock_qdrant):
    with patch("backend.services.knowledge_service.settings") as s, \
         patch("backend.services.knowledge_service.get_dense_model") as MockDense, \
         patch("backend.services.knowledge_service.get_sparse_model") as MockSparse:
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

    mock_qdrant.search.assert_not_called()
    assert results == []


def test_search_qdrant_error_raises(service, mock_qdrant):
    """Erro do Qdrant deve ser propagado como exceção."""
    mock_qdrant.query_points.side_effect = Exception("Qdrant connection timeout")

    with pytest.raises(Exception, match="Qdrant connection timeout"):
        service.search("Como abrir um chamado?")


def test_search_limits_results(service, mock_qdrant):
    """Busca deve respeitar top_k — retorna no máximo N resultados via RRF."""
    hits = [_make_hit(f"texto {i}", f"fonte_{i}.pdf", score=0.9 - i * 0.1) for i in range(10)]
    mock_qdrant.search.return_value = hits

    results = service.search("test query", top_k=3)

    assert len(results) <= 3


def test_list_sources_retorna_lista_vazia_e_loga_em_caso_de_erro(service, mock_qdrant):
    """Erro no scroll deve ser capturado, logado e retornar lista vazia."""
    mock_qdrant.scroll.side_effect = Exception("Qdrant indisponível")
    result = service.list_sources()
    assert result == []


def test_search_with_coverage_adds_missing_source(service, mock_qdrant):
    """search_with_coverage deve incluir chunk de fonte não coberta pela busca semântica."""
    # Busca semântica (query_points) retorna só fonte_a
    hit_a = _make_hit("conteúdo A", "fonte_a.pdf", score=0.9)
    mock_qdrant.query_points.return_value = _query_points_result([hit_a])

    # list_sources: fonte_a e fonte_b existem no Qdrant
    source_point_a = MagicMock()
    source_point_a.payload = {"source": "fonte_a.pdf"}
    source_point_b = MagicMock()
    source_point_b.payload = {"source": "fonte_b.pdf"}

    # chunk representativo da fonte_b (scroll com filtro)
    chunk_b = MagicMock()
    chunk_b.payload = {"text": "conteúdo B", "source": "fonte_b.pdf"}

    # Primeira chamada scroll → list_sources; segunda → chunk de fonte_b
    mock_qdrant.scroll.side_effect = [
        ([source_point_a, source_point_b], None),
        ([chunk_b], None),
    ]

    results, sources = service.search_with_coverage("alguma query")

    sources_in_results = {r["source"] for r in results}
    assert "fonte_a.pdf" in sources_in_results
    assert "fonte_b.pdf" in sources_in_results


def test_search_rrf_merges_dense_and_sparse(service, mock_qdrant):
    """Hit que aparece em dense e sparse deve ter score RRF maior que hit exclusivo."""
    shared_hit = _make_hit("texto compartilhado", "fonte.pdf")
    shared_hit.id = "shared-id"
    exclusive_hit = _make_hit("texto exclusivo", "outro.pdf")
    exclusive_hit.id = "exclusive-id"

    # Primeira chamada (dense): shared + exclusive; segunda (sparse): só shared
    mock_qdrant.query_points.side_effect = [
        _query_points_result([shared_hit, exclusive_hit]),
        _query_points_result([shared_hit]),
    ]

    results = service.search("query teste", top_k=2)

    # shared deve aparecer primeiro (score RRF maior)
    assert results[0]["text"] == "texto compartilhado"


def test_list_sources_paginacao_multiplas_paginas(service, mock_qdrant):
    """list_sources deve paginar via scroll cursor até next_offset=None."""
    page1_point = MagicMock()
    page1_point.payload = {"source": "fonte_a.pdf"}
    page2_point = MagicMock()
    page2_point.payload = {"source": "fonte_b.pdf"}

    # Primeira chamada retorna next_offset="cursor-1"; segunda retorna None (fim)
    mock_qdrant.scroll.side_effect = [
        ([page1_point], "cursor-1"),
        ([page2_point], None),
    ]

    result = service.list_sources()

    assert mock_qdrant.scroll.call_count == 2
    assert "fonte_a.pdf" in result
    assert "fonte_b.pdf" in result
    assert result == sorted(result)  # sempre retorna ordenado


def test_list_sources_deduplica_fonte_repetida(service, mock_qdrant):
    """list_sources deve deduplicar a mesma fonte que aparece em múltiplos pontos."""
    point_a1 = MagicMock()
    point_a1.payload = {"source": "fonte_a.pdf"}
    point_a2 = MagicMock()
    point_a2.payload = {"source": "fonte_a.pdf"}  # duplicata

    mock_qdrant.scroll.return_value = ([point_a1, point_a2], None)

    result = service.list_sources()

    assert result == ["fonte_a.pdf"]  # uma só ocorrência

"""Testes unitários para o agente RAG (LangGraph).

Conforme especificado no Execution Plan §2.1.5:
  - graph compila
  - query simples retorna resposta
  - estados de erro tratados
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.rag_agent import AgentState, build_rag_graph


@pytest.fixture()
def knowledge_service():
    svc = MagicMock()
    svc.search_with_coverage.return_value = [
        {"text": "Férias são 30 dias corridos.", "source": "manual_ferias.pdf", "score": 0.95}
    ]
    return svc


@pytest.fixture()
def chat_service():
    svc = MagicMock()
    svc.generate_stream.return_value = iter(["Você tem ", "30 dias ", "de férias."])
    return svc


@pytest.fixture()
def rag_graph(knowledge_service, chat_service):
    return build_rag_graph(knowledge_service, chat_service)


def test_graph_compiles(knowledge_service, chat_service):
    """O grafo deve compilar sem erros."""
    graph = build_rag_graph(knowledge_service, chat_service)
    assert graph is not None


def test_graph_returns_response(rag_graph, knowledge_service, chat_service):
    """Query simples deve percorrer retrieve→generate e retornar chunks."""
    initial: AgentState = {
        "query": "Quantos dias de férias tenho?",
        "context": [],
        "sources": [],
        "response_chunks": [],
        "error": None,
    }

    result = rag_graph.invoke(initial)

    knowledge_service.search_with_coverage.assert_called_once_with("Quantos dias de férias tenho?")
    chat_service.generate_stream.assert_called_once()
    assert result["response_chunks"] == ["Você tem ", "30 dias ", "de férias."]


def test_graph_passes_context_to_generate(rag_graph, knowledge_service, chat_service):
    """Os chunks recuperados pelo retrieve devem ser passados ao generate."""
    initial: AgentState = {
        "query": "Política de reembolso?",
        "context": [],
        "sources": [],
        "response_chunks": [],
        "error": None,
    }

    rag_graph.invoke(initial)

    _, kwargs = chat_service.generate_stream.call_args
    context_arg = kwargs.get("context") or chat_service.generate_stream.call_args[0][1]
    assert len(context_arg) == 1
    assert context_arg[0]["source"] == "manual_ferias.pdf"


def test_graph_empty_context_still_generates(knowledge_service, chat_service):
    """Qdrant sem resultados não deve impedir a geração de resposta."""
    knowledge_service.search_with_coverage.return_value = []
    chat_service.generate_stream.return_value = iter(["Não encontrei informações."])

    graph = build_rag_graph(knowledge_service, chat_service)
    initial: AgentState = {
        "query": "Pergunta sem contexto",
        "context": [],
        "sources": [],
        "response_chunks": [],
        "error": None,
    }

    result = graph.invoke(initial)

    assert result["response_chunks"] == ["Não encontrei informações."]


def test_graph_propagates_knowledge_error(knowledge_service, chat_service):
    """Erro no KnowledgeService deve ser propagado (não silenciado)."""
    knowledge_service.search_with_coverage.side_effect = Exception("Qdrant timeout")

    graph = build_rag_graph(knowledge_service, chat_service)
    initial: AgentState = {
        "query": "teste",
        "context": [],
        "sources": [],
        "response_chunks": [],
        "error": None,
    }

    with pytest.raises(Exception, match="Qdrant timeout"):
        graph.invoke(initial)

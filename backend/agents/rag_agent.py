"""Agente RAG com LangGraph: retrieve → generate."""
from typing import Any, TypedDict

import structlog
from langgraph.graph import END, StateGraph

from backend.services.chat_service import ChatService
from backend.services.knowledge_service import KnowledgeService

logger = structlog.get_logger()


class AgentState(TypedDict):
    query: str
    context: list[dict[str, Any]]
    sources: list[str]
    response_chunks: list[str]
    error: str | None


def build_rag_graph(
    knowledge_service: KnowledgeService,
    chat_service: ChatService,
) -> Any:
    """Constrói e compila o grafo RAG."""

    def retrieve(state: AgentState) -> AgentState:
        logger.info("rag_retrieve", query=state["query"][:50])
        # search_with_coverage retorna (results, sources) — uma única chamada ao Qdrant
        context, sources = knowledge_service.search_with_coverage(state["query"])
        return {**state, "context": context, "sources": sources}

    def generate(state: AgentState) -> AgentState:
        logger.info("rag_generate", context_chunks=len(state["context"]))
        chunks = list(
            chat_service.generate_stream(state["query"], state["context"], state.get("sources"))
        )
        return {**state, "response_chunks": chunks}

    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()

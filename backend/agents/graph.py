# backend/agents/graph.py
"""
Grafo LangGraph com agentes especializados.
Orquestra o fluxo: classificação de intenção → retrieval → geração → validação.
"""

import asyncio
from typing import AsyncGenerator, TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
import anthropic

from .search_agent import SearchAgent
from .video_agent import VideoAgent
from .doc_agent import DocAgent
from .compliance_agent import ComplianceAgent
from .memory_agent import MemoryAgent
from .evaluator_agent import EvaluatorAgent
from ..services.prompt_service import load_system_prompt


# ─── State ───────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    question:        str
    conversation_id: str
    history:         list[dict]
    user_groups:     list[str]
    user_id:         str
    intent:          str          # 'video' | 'document' | 'general' | 'policy'
    chunks:          list[dict]   # retrieved chunks com metadados
    answer:          str          # resposta gerada pelo Claude
    sources:         list[dict]   # fontes formatadas para o Angular
    approved:        bool         # passou na validação de compliance
    ragas_score:     float


# ─── Nodes ────────────────────────────────────────────────────────────────────

async def classify_intent(state: AgentState) -> AgentState:
    """Classifica a intenção da pergunta para rotear ao agente correto."""
    q = state["question"].lower()

    if any(kw in q for kw in ["vídeo", "video", "minuto", "timestamp", "assiste"]):
        intent = "video"
    elif any(kw in q for kw in ["política", "policy", "regra", "compliance", "norma"]):
        intent = "policy"
    elif any(kw in q for kw in ["documento", "pdf", "manual", "página"]):
        intent = "document"
    else:
        intent = "general"

    return {**state, "intent": intent}


async def retrieve(state: AgentState) -> AgentState:
    """Retrieval híbrido com filtro de permissão."""
    agent = SearchAgent()
    chunks = await agent.search(
        query=state["question"],
        user_groups=state["user_groups"],
        intent=state["intent"],
    )
    return {**state, "chunks": chunks}


async def enrich_video(state: AgentState) -> AgentState:
    """Enriquece chunks de vídeo com timestamps formatados."""
    agent = VideoAgent()
    chunks = await agent.enrich(state["chunks"], state["question"])
    return {**state, "chunks": chunks}


async def generate_answer(state: AgentState) -> AgentState:
    """Geração de resposta com Claude claude-opus-4-5."""
    client = anthropic.AsyncAnthropic()

    system_prompt = load_system_prompt()
    context = _format_context(state["chunks"])

    messages = [
        *state["history"][-6:],   # últimas 6 trocas para contexto
        {"role": "user", "content": f"Contexto:\n{context}\n\nPergunta: {state['question']}"}
    ]

    response = await client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        system=system_prompt,
        messages=messages,
    )

    answer = response.content[0].text
    sources = _format_sources(state["chunks"])

    return {**state, "answer": answer, "sources": sources}


async def validate_compliance(state: AgentState) -> AgentState:
    """Valida se a resposta não vaza conteúdo além das permissões."""
    agent = ComplianceAgent()
    approved = await agent.validate(
        answer=state["answer"],
        chunks=state["chunks"],
        user_groups=state["user_groups"],
    )
    return {**state, "approved": approved}


async def evaluate_quality(state: AgentState) -> AgentState:
    """Calcula RAGAS score da resposta (background, não bloqueia o stream)."""
    agent = EvaluatorAgent()
    score = await agent.evaluate_async(
        question=state["question"],
        answer=state["answer"],
        chunks=state["chunks"],
        user_id=state["user_id"],
        conversation_id=state["conversation_id"],
    )
    return {**state, "ragas_score": score}


def route_by_intent(state: AgentState) -> Literal["enrich_video", "generate_answer"]:
    return "enrich_video" if state["intent"] == "video" else "generate_answer"


def route_compliance(state: AgentState) -> Literal["evaluate_quality", END]:
    return "evaluate_quality" if state["approved"] else END


# ─── Build Graph ─────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(AgentState)

    g.add_node("classify_intent",     classify_intent)
    g.add_node("retrieve",            retrieve)
    g.add_node("enrich_video",        enrich_video)
    g.add_node("generate_answer",     generate_answer)
    g.add_node("validate_compliance", validate_compliance)
    g.add_node("evaluate_quality",    evaluate_quality)

    g.set_entry_point("classify_intent")
    g.add_edge("classify_intent", "retrieve")
    g.add_conditional_edges("retrieve", route_by_intent)
    g.add_edge("enrich_video", "generate_answer")
    g.add_edge("generate_answer", "validate_compliance")
    g.add_conditional_edges("validate_compliance", route_compliance)
    g.add_edge("evaluate_quality", END)

    return g.compile()


GRAPH = build_graph()


# ─── Streaming Entry Point ────────────────────────────────────────────────────

async def run_agent_stream(
    question: str,
    conversation_id: str,
    history: list[dict],
    user_groups: list[str],
    user_id: str,
) -> AsyncGenerator[dict, None]:
    """
    Roda o grafo e emite chunks SSE para o Angular.
    Faz streaming real do Claude via Anthropic SDK enquanto o grafo processa.
    """
    client = anthropic.AsyncAnthropic()

    # 1. Classify + Retrieve (rápido, sem streaming)
    state: AgentState = {
        "question": question, "conversation_id": conversation_id,
        "history": history, "user_groups": user_groups, "user_id": user_id,
        "intent": "", "chunks": [], "answer": "", "sources": [],
        "approved": True, "ragas_score": 0.0,
    }
    state = await classify_intent(state)
    state = await retrieve(state)
    if state["intent"] == "video":
        state = await enrich_video(state)

    # 2. Compliance check rápido nos chunks
    agent = ComplianceAgent()
    if not await agent.validate_chunks(state["chunks"], user_groups):
        yield {"type": "error", "error": "Você não tem permissão para acessar este conteúdo."}
        return

    # 3. Streaming do Claude
    system_prompt = load_system_prompt()
    context = _format_context(state["chunks"])
    messages = [
        *history[-6:],
        {"role": "user", "content": f"Contexto:\n{context}\n\nPergunta: {question}"}
    ]

    full_answer = ""
    async with client.messages.stream(
        model="claude-opus-4-5",
        max_tokens=1500,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            full_answer += text
            yield {"type": "token", "text": text}

    # 4. Emit sources
    sources = _format_sources(state["chunks"])
    yield {"type": "sources", "sources": sources}

    # 5. Done
    yield {"type": "done"}

    # 6. RAGAS em background (não bloqueia o stream)
    asyncio.create_task(
        EvaluatorAgent().evaluate_async(
            question=question, answer=full_answer,
            chunks=state["chunks"], user_id=user_id,
            conversation_id=conversation_id,
        )
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _format_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        ts = f" [{c['timestamp_start']} → {c['timestamp_end']}]" if c.get("timestamp_start") else ""
        pg = f" [p. {c['page']}]" if c.get("page") else ""
        parts.append(f"[{i}] {c['source_name']}{ts}{pg}:\n{c['content']}\n")
    return "\n".join(parts)


def _format_sources(chunks: list[dict]) -> list[dict]:
    seen = set()
    sources = []
    for c in chunks:
        key = c["source_name"] + str(c.get("timestamp_start", ""))
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "id":                c["id"],
            "type":              c["source_type"],
            "name":              c["source_name"],
            "url":               c["source_url"],
            "page":              c.get("page"),
            "timestamp_start":   c.get("timestamp_start_seconds"),
            "timestamp_end":     c.get("timestamp_end_seconds"),
            "sensitivity_label": c["sensitivity_label"],
            "relevance_score":   c.get("@search.reranker_score", 0.8),
        })
    return sources[:5]   # máximo 5 fontes por resposta

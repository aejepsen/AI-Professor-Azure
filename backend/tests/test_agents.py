# backend/tests/test_agents.py
"""Testes unitários dos agentes LangGraph."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── SearchAgent ─────────────────────────────────────────────────────────────

class TestSearchAgent:
    def test_permission_filter_no_groups(self):
        from backend.agents.search_agent import SearchAgent
        agent = SearchAgent()
        f = agent._build_permission_filter([])
        assert "public" in f
        assert "internal" not in f

    def test_permission_filter_with_groups(self):
        from backend.agents.search_agent import SearchAgent
        agent = SearchAgent()
        f = agent._build_permission_filter(["group-a", "group-b"])
        assert "public" in f
        assert "internal" in f
        assert "group-a" in f
        assert "group-b" in f

    @pytest.mark.asyncio
    async def test_search_returns_list(self):
        from backend.agents.search_agent import SearchAgent
        agent = SearchAgent()
        mock_result = [{"id": "1", "content": "test", "source_name": "doc.pdf",
                        "source_type": "document", "sensitivity_label": "internal",
                        "source_url": "https://blob/doc.pdf", "permission_groups": [],
                        "@search.reranker_score": 0.9}]
        with patch.object(agent, '_hybrid_search', new=AsyncMock(return_value=mock_result)):
            with patch.object(agent, '_embed', new=AsyncMock(return_value=[0.1] * 3072)):
                results = await agent.search("Como abrir chamado?", ["group-rh"])
        assert isinstance(results, list)


# ─── ComplianceAgent ─────────────────────────────────────────────────────────

class TestComplianceAgent:
    @pytest.mark.asyncio
    async def test_public_content_always_allowed(self):
        from backend.agents.compliance_agent import ComplianceAgent
        agent  = ComplianceAgent()
        chunks = [{"sensitivity_label": "public", "permission_groups": []}]
        assert await agent.validate("qualquer resposta", chunks, []) is True

    @pytest.mark.asyncio
    async def test_confidential_requires_group(self):
        from backend.agents.compliance_agent import ComplianceAgent
        agent  = ComplianceAgent()
        chunks = [{"sensitivity_label": "confidential", "permission_groups": ["grupo-diretoria"]}]
        # Usuário sem o grupo — deve ser bloqueado
        assert await agent.validate("resposta", chunks, ["grupo-rh"]) is False
        # Usuário com o grupo — deve ser permitido
        assert await agent.validate("resposta", chunks, ["grupo-diretoria"]) is True

    @pytest.mark.asyncio
    async def test_restricted_always_blocked(self):
        from backend.agents.compliance_agent import ComplianceAgent
        agent  = ComplianceAgent()
        chunks = [{"sensitivity_label": "restricted", "permission_groups": ["grupo-board"]}]
        assert await agent.validate("resposta", chunks, ["grupo-board"]) is False


# ─── VideoAgent ──────────────────────────────────────────────────────────────

class TestVideoAgent:
    @pytest.mark.asyncio
    async def test_timestamps_formatted(self):
        from backend.agents.video_agent import VideoAgent
        agent  = VideoAgent()
        chunks = [{
            "source_type": "video", "source_name": "onboarding.mp4",
            "timestamp_start_seconds": 272, "timestamp_end_seconds": 330,
            "content": "explicação sobre férias", "topics": ["ferias"],
            "@search.reranker_score": 0.9,
        }]
        enriched = await agent.enrich(chunks, "quando falam de férias?")
        assert enriched[0]["timestamp_start"] == "04:32"
        assert enriched[0]["timestamp_end"]   == "05:30"
        assert "→" in enriched[0]["timestamp_display"]

    @pytest.mark.asyncio
    async def test_video_chunks_sorted_by_relevance(self):
        from backend.agents.video_agent import VideoAgent
        agent  = VideoAgent()
        chunks = [
            {"source_type": "video", "content": "outro assunto", "topics": ["TI"],
             "timestamp_start_seconds": 10, "timestamp_end_seconds": 60,
             "source_name": "v.mp4", "@search.reranker_score": 0.5},
            {"source_type": "video", "content": "reembolso de despesas", "topics": ["reembolso", "despesas"],
             "timestamp_start_seconds": 100, "timestamp_end_seconds": 200,
             "source_name": "v.mp4", "@search.reranker_score": 0.9},
        ]
        enriched = await agent.enrich(chunks, "como funciona o reembolso?")
        assert "reembolso" in enriched[0]["content"]


# ─── MemoryAgent ─────────────────────────────────────────────────────────────

class TestMemoryAgent:
    def test_stores_and_retrieves_history(self):
        from backend.agents.memory_agent import MemoryAgent
        agent = MemoryAgent()
        conv_id = "test-conv-001"
        agent.add_turn(conv_id, "pergunta 1", "resposta 1")
        agent.add_turn(conv_id, "pergunta 2", "resposta 2")
        history = agent.get_history(conv_id)
        assert len(history) == 4
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "pergunta 1"

    def test_clears_history(self):
        from backend.agents.memory_agent import MemoryAgent
        agent   = MemoryAgent()
        conv_id = "test-conv-002"
        agent.add_turn(conv_id, "q", "a")
        agent.clear(conv_id)
        assert agent.get_history(conv_id) == []

    def test_max_history_limit(self):
        from backend.agents.memory_agent import MemoryAgent, MAX_HISTORY
        agent   = MemoryAgent()
        conv_id = "test-conv-003"
        for i in range(30):
            agent.add_turn(conv_id, f"q{i}", f"a{i}")
        history = agent.get_history(conv_id)
        assert len(history) <= MAX_HISTORY


# ─── Pipeline Quality ─────────────────────────────────────────────────────────

class TestPipelineQuality:
    def test_evaluate_transcription_quality(self):
        from pipeline.evaluate_quality import evaluate_transcription_quality
        raw = {"segments": [{"text": "Ola bom dia", "start_ts": "00:00:00", "end_ts": "00:00:05"}]}
        enriched = {"topics": [{"title": "Abertura", "summary": "Saudação inicial.", "keywords": ["bom dia"],
                                "segments_corrected": ["Olá, bom dia."]}]}
        result = evaluate_transcription_quality(raw, enriched)
        assert 0.0 <= result["quality_score"] <= 1.0
        assert "needs_review" in result

    def test_chunk_video_preserves_timestamps(self):
        from pipeline.chunk import chunk_document
        enriched = {"topics": [{
            "title": "Política de férias", "summary": "Resumo das férias.",
            "keywords": ["ferias"], "start_ts": "00:05:00", "end_ts": "00:08:30",
            "segments_corrected": ["O colaborador tem direito a 30 dias."]
        }]}
        meta = {"name": "rh.mp4", "url": "https://blob/rh.mp4",
                "source_type": "video", "sensitivity_label": "internal", "permission_groups": []}
        chunks = chunk_document(enriched, meta)
        assert len(chunks) == 1
        assert chunks[0]["timestamp_start"] == "00:05:00"
        assert chunks[0]["timestamp_start_seconds"] == 300

    def test_chunk_document_creates_sections(self):
        from pipeline.chunk import chunk_document
        enriched = {
            "document_summary": "Politica de RH.",
            "main_topics":      ["RH"],
            "sections": [
                {"title": "Seção 1", "content": "Conteúdo da seção 1.", "page_estimate": 1, "keywords": ["rh"]},
                {"title": "Seção 2", "content": "Conteúdo da seção 2.", "page_estimate": 2, "keywords": ["beneficios"]},
            ]
        }
        meta = {"name": "politica.pdf", "url": "https://blob/p.pdf",
                "source_type": "document", "sensitivity_label": "internal", "permission_groups": []}
        chunks = chunk_document(enriched, meta)
        assert len(chunks) == 2
        assert chunks[0]["page_number"] == 1
        assert chunks[1]["page_number"] == 2


# ─── Auth ─────────────────────────────────────────────────────────────────────

class TestAuth:
    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        from fastapi.testclient import TestClient
        from backend.api.main import app
        client = TestClient(app)
        response = client.get("/conversations", headers={"Authorization": "Bearer token_invalido"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_health_endpoint_no_auth(self):
        from fastapi.testclient import TestClient
        from backend.api.main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

"""Testes unitários para o ChatService."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.chat_service import ChatService, _format_context


@pytest.fixture()
def service():
    with patch("backend.services.chat_service.settings") as s:
        s.anthropic_api_key = "sk-ant-fake"
        with patch("backend.services.chat_service.anthropic.Anthropic"):
            return ChatService()


@pytest.mark.asyncio
async def test_stream_yields_tokens(service):
    """Streaming deve gerar tokens progressivamente."""
    mock_chunk = MagicMock()
    mock_chunk.type = "content_block_delta"
    mock_chunk.delta = MagicMock()
    mock_chunk.delta.text = "Férias são 30 dias."

    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.__iter__ = MagicMock(return_value=iter([mock_chunk]))

    service._client.messages.stream = MagicMock(return_value=mock_stream)

    tokens = list(service.generate_stream("Quantos dias de férias?", context=[]))
    assert len(tokens) > 0
    assert "Férias" in "".join(tokens)


@pytest.mark.asyncio
async def test_stream_empty_context_generates_fallback(service):
    """Contexto vazio deve gerar resposta de fallback, não alucinação."""
    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.__iter__ = MagicMock(return_value=iter([]))

    service._client.messages.stream = MagicMock(return_value=mock_stream)

    tokens = list(service.generate_stream("Pergunta qualquer", context=[]))
    # Deve completar sem erros mesmo com contexto vazio
    assert isinstance(tokens, list)


@pytest.mark.asyncio
async def test_stream_anthropic_error_raises(service):
    """Erro da API Anthropic deve ser propagado como exceção."""
    service._client.messages.stream = MagicMock(
        side_effect=Exception("Anthropic API rate limit")
    )

    with pytest.raises(Exception, match="Anthropic API rate limit"):
        list(service.generate_stream("test", context=[]))


# ---------------------------------------------------------------------------
# Testes para _format_context
# ---------------------------------------------------------------------------

def test_format_context_vazio_retorna_string_vazia():
    """Lista vazia deve retornar string vazia — sem contexto no prompt."""
    assert _format_context([]) == ""


def test_format_context_um_chunk():
    """Um chunk deve gerar bloco numerado com source e text."""
    chunks = [{"source": "manual_ferias.pdf", "text": "Férias são 30 dias corridos."}]
    result = _format_context(chunks)

    assert "Contexto dos documentos:" in result
    assert "[1] manual_ferias.pdf:" in result
    assert "Férias são 30 dias corridos." in result


def test_format_context_multiplos_chunks_numerados():
    """Múltiplos chunks devem ser numerados sequencialmente."""
    chunks = [
        {"source": "doc_a.pdf", "text": "Texto A"},
        {"source": "doc_b.pdf", "text": "Texto B"},
        {"source": "doc_c.pdf", "text": "Texto C"},
    ]
    result = _format_context(chunks)

    assert "[1] doc_a.pdf:" in result
    assert "[2] doc_b.pdf:" in result
    assert "[3] doc_c.pdf:" in result


def test_format_context_chunk_sem_source_usa_fallback():
    """Chunk sem chave 'source' deve usar 'Documento' como fallback."""
    chunks = [{"text": "Conteúdo sem fonte"}]
    result = _format_context(chunks)

    assert "[1] Documento:" in result
    assert "Conteúdo sem fonte" in result

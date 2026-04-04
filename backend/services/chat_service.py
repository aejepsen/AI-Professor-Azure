"""Serviço de geração de respostas via Claude Sonnet com streaming."""
from collections.abc import Iterator
from typing import Any

import anthropic
import structlog

from backend.core.config import settings

logger = structlog.get_logger()

SYSTEM_PROMPT = """Você é o AI Professor, assistente corporativo especializado em políticas e
procedimentos da empresa. Responda apenas com base no contexto fornecido.
Se a informação não estiver no contexto, diga claramente que não encontrou a
resposta nos documentos disponíveis. Não invente informações."""

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024


class ChatService:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def generate_stream(
        self, query: str, context: list[dict[str, Any]]
    ) -> Iterator[str]:
        """
        Gera resposta em streaming usando Claude Sonnet.

        Args:
            query: Pergunta do usuário.
            context: Lista de chunks recuperados do Qdrant.

        Yields:
            Fragmentos de texto conforme são gerados.
        """
        context_text = _format_context(context)
        user_message = f"{context_text}\n\nPergunta: {query}" if context_text else query

        logger.info("chat_stream_start", query_len=len(query), context_chunks=len(context))

        with self._client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for event in stream:
                if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                    yield event.delta.text


def _format_context(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        source = chunk.get("source", "Documento")
        text = chunk.get("text", "")
        parts.append(f"[{i}] {source}:\n{text}")
    return "Contexto dos documentos:\n\n" + "\n\n".join(parts)

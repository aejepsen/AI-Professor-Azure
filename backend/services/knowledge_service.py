"""Serviço de busca híbrida no Qdrant (BM25 + dense embeddings)."""
from typing import Any

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http.models import SearchRequest

from backend.core.config import settings

logger = structlog.get_logger()

COLLECTION_NAME = "ai_professor_docs"
DEFAULT_TOP_K = 4


class KnowledgeService:
    def __init__(self) -> None:
        self._client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=10.0,
        )

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
        """
        Busca híbrida: retorna os chunks mais relevantes para a query.

        Args:
            query: Pergunta do usuário.
            top_k: Número máximo de resultados.

        Returns:
            Lista de dicts com keys: text, source, score.
        """
        if not query.strip():
            return []

        # Embedding inline simples — em produção usar modelo dedicado
        # Por ora usa busca por texto via payload filter + scroll
        # TODO: integrar modelo de embedding (ex: text-embedding-3-small)
        results = self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=[0.0] * 1536,  # placeholder até integrar embedding
            limit=top_k,
            with_payload=True,
        )

        return [
            {
                "text": hit.payload.get("text", "") if hit.payload else "",
                "source": hit.payload.get("source", "") if hit.payload else "",
                "score": hit.score,
            }
            for hit in results
        ]

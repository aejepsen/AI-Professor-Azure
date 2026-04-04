"""Serviço de busca semântica no Qdrant usando sentence-transformers."""
from typing import Any

import structlog
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from backend.core.config import settings

logger = structlog.get_logger()

COLLECTION_NAME = "ai_professor_docs"
DEFAULT_TOP_K = 4
EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"


class KnowledgeService:
    def __init__(self) -> None:
        self._client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=10.0,
        )
        self._embedder = SentenceTransformer(EMBED_MODEL)

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
        """
        Busca semântica: retorna os chunks mais relevantes para a query.

        Args:
            query: Pergunta do usuário.
            top_k: Número máximo de resultados.

        Returns:
            Lista de dicts com keys: text, source, score.
        """
        if not query.strip():
            return []

        vector = self._embedder.encode(query, normalize_embeddings=True).tolist()

        results = self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
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

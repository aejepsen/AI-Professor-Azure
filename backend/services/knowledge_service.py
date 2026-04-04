"""Serviço de busca híbrida no Qdrant (dense e5-large + BM25 sparse, fusão RRF)."""
from typing import Any

import structlog
from fastembed.sparse.bm25 import Bm25
from qdrant_client import QdrantClient
from qdrant_client.http.models import Fusion, Prefetch, SparseVector
from sentence_transformers import SentenceTransformer

from backend.core.config import settings

logger = structlog.get_logger()

COLLECTION_NAME = "ai_professor_docs"
DEFAULT_TOP_K = 4
DENSE_MODEL = "intfloat/multilingual-e5-large"
SPARSE_MODEL = "Qdrant/bm25"


class KnowledgeService:
    def __init__(self) -> None:
        self._client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=10.0,
        )
        self._dense = SentenceTransformer(DENSE_MODEL)
        self._sparse = Bm25(SPARSE_MODEL)

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
        """
        Busca híbrida (dense + BM25 com fusão RRF): retorna os chunks mais relevantes.

        Args:
            query: Pergunta do usuário.
            top_k: Número máximo de resultados.

        Returns:
            Lista de dicts com keys: text, source, score.
        """
        if not query.strip():
            return []

        q_dense = self._dense.encode("query: " + query, normalize_embeddings=True).tolist()
        q_sparse_raw = list(self._sparse.embed([query]))[0]
        q_sparse = SparseVector(
            indices=q_sparse_raw.indices.tolist(),
            values=q_sparse_raw.values.tolist(),
        )

        results = self._client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                Prefetch(query=q_dense, using="dense", limit=top_k * 3),
                Prefetch(query=q_sparse, using="sparse", limit=top_k * 3),
            ],
            query=Fusion.RRF,
            limit=top_k,
            with_payload=True,
        ).points

        return [
            {
                "text": hit.payload.get("text", "") if hit.payload else "",
                "source": hit.payload.get("source", "") if hit.payload else "",
                "score": hit.score,
            }
            for hit in results
        ]

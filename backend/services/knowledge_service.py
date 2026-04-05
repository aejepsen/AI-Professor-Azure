"""Serviço de busca híbrida no Qdrant (dense e5-large + BM25 sparse, fusão RRF)."""
from typing import Any

import structlog
from fastembed.sparse.bm25 import Bm25
from qdrant_client import QdrantClient
from qdrant_client.http.models import NamedSparseVector, NamedVector, SparseVector
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

        fetch_limit = top_k * 3
        dense_hits = self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=NamedVector(name="dense", vector=q_dense),
            limit=fetch_limit,
            with_payload=True,
        )
        sparse_hits = self._client.search(
            collection_name=COLLECTION_NAME,
            query_vector=NamedSparseVector(
                name="sparse",
                vector=SparseVector(
                    indices=q_sparse.indices,
                    values=q_sparse.values,
                ),
            ),
            limit=fetch_limit,
            with_payload=True,
        )

        # RRF manual (k=60)
        k = 60
        scores: dict[str, float] = {}
        payloads: dict[str, dict] = {}

        for rank, hit in enumerate(dense_hits):
            sid = str(hit.id)
            scores[sid] = scores.get(sid, 0.0) + 1 / (k + rank + 1)
            payloads[sid] = hit.payload or {}

        for rank, hit in enumerate(sparse_hits):
            sid = str(hit.id)
            scores[sid] = scores.get(sid, 0.0) + 1 / (k + rank + 1)
            payloads[sid] = hit.payload or {}

        top_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_k]
        return [
            {
                "text": payloads[sid].get("text", ""),
                "source": payloads[sid].get("source", ""),
                "score": scores[sid],
            }
            for sid in top_ids
        ]

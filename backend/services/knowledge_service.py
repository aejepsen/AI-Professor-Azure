"""Serviço de busca híbrida no Qdrant (dense e5-large + BM25 sparse, fusão RRF)."""
from typing import Any

import structlog
from fastembed.sparse.bm25 import Bm25
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue, SparseVector
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

    def list_sources(self) -> list[str]:
        """Retorna lista de fontes únicas indexadas no Qdrant."""
        try:
            result, _ = self._client.scroll(
                collection_name=COLLECTION_NAME,
                limit=1000,
                with_payload=["source"],
                with_vectors=False,
            )
            seen: set[str] = set()
            sources = []
            for point in result:
                src = (point.payload or {}).get("source", "")
                if src and src not in seen:
                    seen.add(src)
                    sources.append(src)
            return sorted(sources)
        except Exception as exc:
            logger.error("list_sources_failed", error=str(exc))
            return []

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
        dense_hits = self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=q_dense,
            using="dense",
            limit=fetch_limit,
            with_payload=True,
        ).points
        sparse_hits = self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=q_sparse,
            using="sparse",
            limit=fetch_limit,
            with_payload=True,
        ).points

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

    def search_with_coverage(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict[str, Any]]:
        """
        Busca híbrida + garante ao menos 1 chunk por fonte indexada.

        Para perguntas genéricas (ex: "liste os temas"), a busca semântica pode
        não retornar chunks de todas as fontes. Este método complementa os
        resultados com um chunk representativo de cada fonte não coberta.
        """
        results = self.search(query, top_k)
        covered = {r["source"] for r in results}

        for source in self.list_sources():
            if source in covered:
                continue
            hits, _ = self._client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[FieldCondition(key="source", match=MatchValue(value=source))]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
            if hits:
                payload = hits[0].payload or {}
                results.append({
                    "text": payload.get("text", ""),
                    "source": payload.get("source", ""),
                    "score": 0.0,
                })
                covered.add(source)

        return results

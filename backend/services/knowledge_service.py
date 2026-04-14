"""Serviço de busca híbrida no Qdrant (dense e5-large + BM25 sparse, fusão RRF)."""
from typing import Any

import structlog
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue, SparseVector

from backend.core.config import settings
from backend.core.models import (
    COLLECTION_NAME,
    DENSE_MODEL_NAME,
    SPARSE_MODEL_NAME,
    get_dense_model,
    get_sparse_model,
)

logger = structlog.get_logger()

DEFAULT_TOP_K = 4


class KnowledgeService:
    def __init__(self) -> None:
        self._client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=10.0,
        )
        self._dense = get_dense_model()
        self._sparse = get_sparse_model()

    def list_sources(self) -> list[str]:
        """Retorna lista de fontes únicas indexadas no Qdrant (scroll completo, sem limite)."""
        try:
            seen: set[str] = set()
            sources: list[str] = []
            offset = None

            while True:
                result, next_offset = self._client.scroll(
                    collection_name=COLLECTION_NAME,
                    limit=1000,
                    with_payload=["source"],
                    with_vectors=False,
                    offset=offset,
                )
                for point in result:
                    src = (point.payload or {}).get("source", "")
                    if src and src not in seen:
                        seen.add(src)
                        sources.append(src)
                if next_offset is None:
                    break
                offset = next_offset

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

    def search_with_coverage(
        self, query: str, top_k: int = DEFAULT_TOP_K
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        Busca híbrida + garante ao menos 1 chunk por fonte indexada.

        Retorna uma tupla (results, sources) para evitar chamar list_sources() duas vezes
        quando o chamador também precisa da lista de fontes.

        Args:
            query: Pergunta do usuário.
            top_k: Número base de resultados da busca semântica.

        Returns:
            Tupla (results, sources) onde results é lista de chunks e sources é
            lista ordenada de todas as fontes indexadas.
        """
        sources = self.list_sources()
        results = self.search(query, top_k)
        covered = {r["source"] for r in results}

        for source in sources:
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

        return results, sources

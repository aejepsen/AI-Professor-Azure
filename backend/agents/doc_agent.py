# backend/agents/doc_agent.py
"""
Agente especializado em documentos PDF/Word.
Extrai e processa chunks de documentos corporativos.
"""

import os
import httpx
from typing import Optional

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION = "ai_professor_docs"


class DocAgent:
    """Busca e enriquece chunks de documentos PDF/Word."""

    async def search(
        self,
        query: str,
        user_groups: list[str],
        top: int = 5,
    ) -> list[dict]:
        """Busca semântica em documentos com filtro de permissão."""
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

        payload = {
            "query": query,
            "limit": top,
            "with_payload": True,
            "filter": {
                "should": [
                    {"key": "sensitivity_label", "match": {"value": "public"}},
                    *[
                        {"key": "allowed_groups", "match": {"value": g}}
                        for g in user_groups
                    ],
                ]
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{QDRANT_URL}/collections/{COLLECTION}/points/query",
                    json=payload,
                    headers=headers,
                )
                data = resp.json()
                return [self._to_chunk(p) for p in data.get("result", {}).get("points", [])]
        except Exception:
            return []

    def _to_chunk(self, point: dict) -> dict:
        payload = point.get("payload", {})
        return {
            "id": point.get("id", ""),
            "content": payload.get("content", ""),
            "source_type": "document",
            "source_name": payload.get("source_name", "Documento"),
            "source_url": payload.get("source_url", ""),
            "page": payload.get("page"),
            "sensitivity_label": payload.get("sensitivity_label", "internal"),
            "allowed_groups": payload.get("allowed_groups", []),
        }

    async def get_by_id(self, doc_id: str) -> Optional[dict]:
        """Recupera um documento por ID para preview."""
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{QDRANT_URL}/collections/{COLLECTION}/points/{doc_id}",
                    headers=headers,
                )
                data = resp.json()
                return self._to_chunk(data.get("result", {}))
        except Exception:
            return None

# backend/services/knowledge_service.py
"""
Serviço de base de conhecimento: lista e busca documentos indexados.
"""

import os
import httpx

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION = "ai_professor_docs"


class KnowledgeService:
    """CRUD e busca na base de conhecimento corporativa."""

    async def list_items(self, user_groups: list[str], limit: int = 50) -> list[dict]:
        """Lista documentos indexados visíveis para o usuário."""
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
                    json={"limit": limit, "with_payload": True, "with_vector": False},
                    headers=headers,
                )
                data = resp.json()
                points = data.get("result", {}).get("points", [])
                return [
                    self._to_item(p) for p in points
                    if self._can_access(p.get("payload", {}), user_groups)
                ]
        except Exception:
            return []

    async def search(
        self, query: str, user_groups: list[str], top: int = 10
    ) -> list[dict]:
        """Busca semântica com filtro de permissão."""
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{QDRANT_URL}/collections/{COLLECTION}/points/query",
                    json={"query": query, "limit": top, "with_payload": True},
                    headers=headers,
                )
                data = resp.json()
                points = data.get("result", {}).get("points", [])
                return [
                    self._to_item(p) for p in points
                    if self._can_access(p.get("payload", {}), user_groups)
                ]
        except Exception:
            return []

    def _to_item(self, point: dict) -> dict:
        p = point.get("payload", {})
        return {
            "id": point.get("id", ""),
            "name": p.get("source_name", ""),
            "type": p.get("source_type", "document"),
            "url": p.get("source_url", ""),
            "sensitivity_label": p.get("sensitivity_label", "internal"),
            "indexed_at": p.get("indexed_at", ""),
            "page_count": p.get("page_count"),
        }

    def _can_access(self, payload: dict, user_groups: list[str]) -> bool:
        label = payload.get("sensitivity_label", "internal")
        if label in ("public", "internal"):
            return True
        allowed = payload.get("allowed_groups", [])
        return any(g in user_groups for g in allowed)

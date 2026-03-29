import os
import httpx

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION = "ai_professor_docs"


class KnowledgeService:

    async def list_items(self, user_groups: list, limit: int = 50) -> list:
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
                    json={"limit": limit, "with_payload": True, "with_vector": False},
                    headers=headers,
                )
                points = resp.json().get("result", {}).get("points", [])
                return [self._to_item(p) for p in points]
        except Exception:
            return []

    async def search(self, query: str, user_groups: list, top: int = 5) -> list:
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
                    json={
                        "filter": {
                            "must": [{"key": "content", "match": {"text": query}}]
                        },
                        "limit": top,
                        "with_payload": True,
                        "with_vector": False,
                    },
                    headers=headers,
                )
                points = resp.json().get("result", {}).get("points", [])
                if not points:
                    resp2 = await client.post(
                        f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
                        json={"limit": top, "with_payload": True, "with_vector": False},
                        headers=headers,
                    )
                    points = resp2.json().get("result", {}).get("points", [])
                return [self._to_item(p) for p in points]
        except Exception:
            return []

    def _to_item(self, point: dict) -> dict:
        p = point.get("payload", {})
        return {
            "id": str(point.get("id", "")),
            "content": p.get("content", ""),
            "name": p.get("source_name", ""),
            "type": p.get("source_type", "document"),
            "url": p.get("source_url", ""),
            "sensitivity_label": p.get("sensitivity_label", "internal"),
            "source_name": p.get("source_name", ""),
            "source_type": p.get("source_type", "document"),
            "source_url": p.get("source_url", ""),
        }

# backend/agents/memory_agent.py
"""
Agente de memória: gerencia histórico de conversas e preferências do usuário.
Usa Qdrant para armazenar vetores de memória de longo prazo.
"""

import os
import httpx
from datetime import datetime

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION = "ai_professor_memory"

MAX_HISTORY = 50  # máximo de turnos por usuário


class MemoryAgent:
    """Gerencia memória de curto e longo prazo por usuário."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._history: list[dict] = []

    def store(self, question: str, answer: str) -> None:
        """Armazena um par pergunta/resposta no histórico em memória."""
        self._history.append({
            "role": "user",
            "content": question,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self._history.append({
            "role": "assistant",
            "content": answer,
            "timestamp": datetime.utcnow().isoformat(),
        })
        # Limita o histórico
        if len(self._history) > MAX_HISTORY * 2:
            self._history = self._history[-(MAX_HISTORY * 2):]

    def get_history(self, last_n: int = 6) -> list[dict]:
        """Retorna os últimos N pares de mensagens para contexto."""
        msgs = [{"role": m["role"], "content": m["content"]} for m in self._history]
        return msgs[-last_n * 2:]

    def clear(self) -> None:
        """Limpa o histórico em memória."""
        self._history = []

    async def save_to_qdrant(self, fact: str) -> None:
        """Salva um fato importante sobre o usuário no Qdrant para memória persistente."""
        if not QDRANT_URL or not QDRANT_API_KEY:
            return
        # Implementação simplificada - em produção usaria embeddings
        headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.put(
                    f"{QDRANT_URL}/collections/{COLLECTION}/points",
                    json={
                        "points": [{
                            "id": f"{self.user_id}_{datetime.utcnow().timestamp()}",
                            "vector": [0.0] * 1536,  # placeholder
                            "payload": {
                                "user_id": self.user_id,
                                "fact": fact,
                                "created_at": datetime.utcnow().isoformat(),
                            },
                        }]
                    },
                    headers=headers,
                )
        except Exception:
            pass  # Silencioso — não bloqueia o fluxo principal

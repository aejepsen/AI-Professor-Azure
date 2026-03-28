# backend/agents/evaluator_agent.py
"""
Agente de avaliação: calcula RAGAS score em background.
Não bloqueia o streaming — roda como asyncio.create_task.
"""

import os
import logging
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)

API_URL = os.getenv("API_URL", "")
RAGAS_TOKEN = os.getenv("RAGAS_TEST_TOKEN", "")


class EvaluatorAgent:
    """Avalia qualidade das respostas com métricas RAGAS."""

    async def evaluate_async(
        self,
        question: str,
        answer: str,
        chunks: list[dict],
        user_id: str,
        conversation_id: str,
    ) -> float:
        """
        Calcula RAGAS score e registra no backend.
        Executa em background — erros são silenciosos.
        """
        try:
            contexts = [c.get("content", "") for c in chunks[:3]]
            score = self._simple_score(question, answer, contexts)

            # Envia para endpoint de métricas (best-effort)
            await self._report_score(
                conversation_id=conversation_id,
                user_id=user_id,
                question=question,
                answer=answer,
                score=score,
            )
            return score
        except Exception as e:
            logger.debug(f"RAGAS evaluation failed (non-critical): {e}")
            return 0.0

    def _simple_score(self, question: str, answer: str, contexts: list[str]) -> float:
        """
        Score simplificado baseado em heurísticas.
        Em produção, usar ragas.evaluate() com modelos de avaliação.
        """
        if not answer or not contexts:
            return 0.0

        # Faithfulness: palavras da resposta presentes nos contextos
        answer_words = set(answer.lower().split())
        context_words = set(" ".join(contexts).lower().split())
        if not answer_words:
            return 0.0

        overlap = len(answer_words & context_words) / len(answer_words)
        length_score = min(len(answer) / 500, 1.0)

        return round((overlap * 0.7 + length_score * 0.3), 3)

    async def _report_score(
        self,
        conversation_id: str,
        user_id: str,
        question: str,
        answer: str,
        score: float,
    ) -> None:
        """Envia score para endpoint de métricas (best-effort)."""
        if not API_URL:
            return
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                await client.post(
                    f"{API_URL}/internal/ragas-score",
                    json={
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "score": score,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    headers={"Authorization": f"Bearer {RAGAS_TOKEN}"},
                )
        except Exception:
            pass

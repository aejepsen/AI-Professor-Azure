# backend/services/feedback_service.py
"""
Serviço de feedback: registra thumbs up/down e dispara re-avaliação RAGAS.
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Em produção: persistir no Supabase/Cosmos DB
_FEEDBACK_STORE: list[dict] = []


class FeedbackService:
    """Registra e processa feedback dos usuários."""

    @staticmethod
    async def record(
        message_id: str,
        user_id: str,
        positive: bool,
        comment: str | None = None,
    ) -> None:
        """Salva o feedback no store."""
        entry = {
            "message_id": message_id,
            "user_id": user_id,
            "positive": positive,
            "comment": comment,
            "created_at": datetime.utcnow().isoformat(),
        }
        _FEEDBACK_STORE.append(entry)
        logger.info(
            f"Feedback {'positivo' if positive else 'negativo'} "
            f"para mensagem {message_id} de {user_id}"
        )

    @staticmethod
    async def trigger_reeval(message_id: str) -> None:
        """
        Dispara re-avaliação RAGAS para mensagens com feedback negativo.
        Em produção: publicar mensagem na fila de avaliação.
        """
        logger.info(f"Re-avaliação RAGAS agendada para mensagem {message_id}")
        # Placeholder — em produção: Azure Service Bus ou Redis Queue

    @staticmethod
    def get_all() -> list[dict]:
        """Retorna todos os feedbacks (para debug/admin)."""
        return _FEEDBACK_STORE.copy()

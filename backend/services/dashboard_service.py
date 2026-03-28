# backend/services/dashboard_service.py
"""
Serviço de dashboard: métricas agregadas para administradores.
"""

import os
import random
from datetime import datetime, timedelta

import httpx

QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")


class DashboardService:
    """Agrega métricas de uso do AI Professor."""

    async def get_metrics(self) -> dict:
        """
        Retorna métricas agregadas para o DashboardComponent.
        Em produção: consultar Application Insights via REST API.
        """
        now = datetime.utcnow()

        # Métricas de conversas (mock para MVP — substituir por Application Insights)
        return {
            "period": {
                "start": (now - timedelta(days=30)).isoformat(),
                "end": now.isoformat(),
            },
            "conversations": {
                "total": random.randint(150, 300),
                "today": random.randint(5, 20),
                "avg_per_day": round(random.uniform(8, 15), 1),
            },
            "messages": {
                "total": random.randint(800, 2000),
                "avg_per_conversation": round(random.uniform(4, 8), 1),
            },
            "quality": {
                "avg_ragas_score": round(random.uniform(0.72, 0.88), 3),
                "positive_feedback_rate": round(random.uniform(0.78, 0.92), 3),
                "negative_feedback_count": random.randint(5, 25),
            },
            "knowledge_base": {
                "total_documents": random.randint(50, 200),
                "total_videos": random.randint(10, 50),
                "last_indexed": (now - timedelta(hours=random.randint(1, 24))).isoformat(),
            },
            "top_topics": [
                {"topic": "Onboarding", "count": random.randint(20, 60)},
                {"topic": "Benefícios", "count": random.randint(15, 50)},
                {"topic": "Políticas RH", "count": random.randint(10, 40)},
                {"topic": "TI e Sistemas", "count": random.randint(8, 30)},
                {"topic": "Compliance", "count": random.randint(5, 25)},
            ],
        }

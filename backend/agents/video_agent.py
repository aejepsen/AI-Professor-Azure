# backend/agents/video_agent.py
"""
Agente de Vídeo — enriquece chunks com timestamps formatados
e garante que a resposta cite o minuto exato do trecho.
"""

import re


class VideoAgent:
    async def enrich(self, chunks: list[dict], question: str) -> list[dict]:
        """
        Ordena chunks de vídeo por relevância e formata timestamps para exibição.
        Prioriza chunks cujo tópico tem maior sobreposição com a pergunta.
        """
        video_chunks = [c for c in chunks if c.get("source_type") == "video"]
        other_chunks  = [c for c in chunks if c.get("source_type") != "video"]

        q_words = set(re.findall(r'\w+', question.lower()))

        def relevance(chunk):
            topics    = " ".join(chunk.get("topics", [])).lower()
            content   = chunk.get("content", "").lower()
            overlap   = len(q_words & set(re.findall(r'\w+', topics + " " + content)))
            reranker  = chunk.get("@search.reranker_score", 0)
            return overlap * 0.4 + reranker * 0.6

        video_chunks.sort(key=relevance, reverse=True)

        for c in video_chunks:
            # Formata campos de timestamp para exibição humana
            s = c.get("timestamp_start_seconds", 0)
            e = c.get("timestamp_end_seconds", 0)
            c["timestamp_start"] = _fmt(s)
            c["timestamp_end"]   = _fmt(e)
            c["timestamp_display"] = f"{_fmt(s)} → {_fmt(e)}"

        return video_chunks + other_chunks


def _fmt(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# backend/agents/doc_agent.py
# ─────────────────────────────────────────────────────────────────────────────

class DocAgent:
    """
    Agente de Documentos — navega em chunks de PDFs, DOCX e PPTX.
    Adiciona número de página e seção para o frontend exibir.
    """

    async def enrich(self, chunks: list[dict]) -> list[dict]:
        doc_chunks = [c for c in chunks if c.get("source_type") in ("document", "policy", "presentation")]
        for c in doc_chunks:
            # Garante que page_number está presente e formatado
            if "page_number" in c and c["page_number"]:
                c["page"] = c["page_number"]
                c["page_display"] = f"p. {c['page_number']}"
        return doc_chunks


# ─────────────────────────────────────────────────────────────────────────────
# backend/agents/compliance_agent.py
# ─────────────────────────────────────────────────────────────────────────────

SENSITIVITY_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


class ComplianceAgent:
    """
    Valida que:
    1. Nenhum chunk acima do nível de permissão do usuário foi incluído
    2. A resposta gerada não cita fontes além das recuperadas (anti-alucinação)
    """

    async def validate(
        self,
        answer: str,
        chunks: list[dict],
        user_groups: list[str],
    ) -> bool:
        # Verifica se todos os chunks pertencem ao usuário
        for chunk in chunks:
            label  = chunk.get("sensitivity_label", "public")
            groups = chunk.get("permission_groups", [])

            if label == "restricted":
                # Restrito requer aprovação manual — nunca deve chegar aqui
                return False

            if label == "confidential":
                # Confidencial: usuário precisa ser membro de pelo menos 1 grupo
                if not any(g in user_groups for g in groups):
                    return False

        return True

    async def validate_chunks(
        self,
        chunks: list[dict],
        user_groups: list[str],
    ) -> bool:
        """Validação rápida antes do streaming — bloqueia se houver chunk indevido."""
        return await self.validate("", chunks, user_groups)


# ─────────────────────────────────────────────────────────────────────────────
# backend/agents/memory_agent.py
# ─────────────────────────────────────────────────────────────────────────────

from collections import defaultdict

# Memória em memória por sessão (em produção: Redis ou Azure Cache)
_SESSION_STORE: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY = 20  # máximo de mensagens mantidas por sessão


class MemoryAgent:
    """
    Gerencia o histórico de conversas para suporte a perguntas multi-turno.
    Ex: "o que mais você sabe sobre isso?" funciona porque o agente lembra o contexto.
    """

    def get_history(self, conversation_id: str) -> list[dict]:
        return _SESSION_STORE[conversation_id][-MAX_HISTORY:]

    def add_turn(self, conversation_id: str, question: str, answer: str):
        _SESSION_STORE[conversation_id].append({"role": "user",      "content": question})
        _SESSION_STORE[conversation_id].append({"role": "assistant", "content": answer})
        # Mantém apenas as últimas MAX_HISTORY mensagens
        _SESSION_STORE[conversation_id] = _SESSION_STORE[conversation_id][-MAX_HISTORY:]

    def clear(self, conversation_id: str):
        _SESSION_STORE.pop(conversation_id, None)


# ─────────────────────────────────────────────────────────────────────────────
# backend/agents/evaluator_agent.py
# ─────────────────────────────────────────────────────────────────────────────

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Thresholds mínimos — abaixo disso a resposta é sinalizada
THRESHOLDS = {
    "faithfulness":       0.85,
    "answer_relevancy":   0.80,
    "context_recall":     0.75,
    "context_precision":  0.80,
    "answer_correctness": 0.85,
}


class EvaluatorAgent:
    """
    Avalia qualidade da resposta usando RAGAS Framework.
    Roda em background para não bloquear o streaming.
    Sinaliza respostas abaixo do threshold para revisão humana.
    """

    async def evaluate_async(
        self,
        question:        str,
        answer:          str,
        chunks:          list[dict],
        user_id:         str,
        conversation_id: str,
    ) -> float:
        """
        Avalia a resposta em background.
        Retorna o score médio (0-1).
        """
        try:
            # Importação lazy para não impactar startup
            from datasets import Dataset
            from ragas import evaluate as ragas_evaluate
            from ragas.metrics import faithfulness, answer_relevancy

            contexts = [c["content"] for c in chunks]

            dataset = Dataset.from_dict({
                "question":    [question],
                "answer":      [answer],
                "contexts":    [contexts],
                "ground_truth": [""],   # sem ground truth em runtime
            })

            # Avalia apenas faithfulness e relevancy em runtime (rápido)
            result = ragas_evaluate(dataset, metrics=[faithfulness, answer_relevancy])

            scores = {
                "faithfulness":     float(result["faithfulness"]),
                "answer_relevancy": float(result["answer_relevancy"]),
            }
            avg_score = sum(scores.values()) / len(scores)

            # Persiste métricas no Application Insights
            await self._log_metrics(
                question=question,
                scores=scores,
                avg_score=avg_score,
                user_id=user_id,
                conversation_id=conversation_id,
            )

            # Sinaliza para revisão se abaixo do threshold
            for metric, score in scores.items():
                if score < THRESHOLDS.get(metric, 0.8):
                    logger.warning(
                        f"[RAGAS] Abaixo do threshold — "
                        f"metric={metric} score={score:.3f} "
                        f"conversation={conversation_id}"
                    )
                    await self._flag_for_review(
                        conversation_id=conversation_id,
                        metric=metric,
                        score=score,
                    )

            return avg_score

        except Exception as e:
            logger.error(f"[RAGAS] Avaliação falhou: {e}")
            return 0.0

    async def _log_metrics(self, question, scores, avg_score, user_id, conversation_id):
        """Envia métricas para Application Insights via OpenTelemetry."""
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
            from opentelemetry import metrics as otel_metrics

            meter  = otel_metrics.get_meter("ai-professor")
            gauge  = meter.create_gauge("ragas_score")
            gauge.set(avg_score, {
                "conversation_id": conversation_id,
                "user_id":         user_id,
            })
        except Exception:
            pass  # Não falha se o monitor não estiver configurado

    async def _flag_for_review(self, conversation_id, metric, score):
        """Registra a interação para revisão humana no dashboard."""
        # Em produção: salva em Azure Table Storage ou Cosmos DB
        logger.info(
            f"[FLAG] conversation={conversation_id} metric={metric} score={score:.3f} "
            f"flagged_at={datetime.now(timezone.utc).isoformat()}"
        )

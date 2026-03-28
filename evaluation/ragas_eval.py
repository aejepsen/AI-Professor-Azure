# evaluation/ragas_eval.py
"""
Avaliação automática de qualidade usando RAGAS Framework.
Executa em CI/CD pós-deploy e periodicamente em produção.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from datasets import Dataset
from ragas import evaluate
from ragas.metrics.collections import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
    answer_correctness,
)
from ragas.llms import LangchainLLMWrapper
from langchain_anthropic import ChatAnthropic
import os as _os

# Configura RAGAS para usar Anthropic ao invés de OpenAI
_anthropic_llm = LangchainLLMWrapper(ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    api_key=_os.getenv("ANTHROPIC_API_KEY", ""),
))
for _m in [faithfulness, answer_relevancy, context_recall, context_precision, answer_correctness]:
    _m.llm = _anthropic_llm


# Dataset de avaliação — perguntas com ground truth conhecidas
EVAL_DATASET = [
    {
        "question":  "Como abrir um chamado de TI?",
        "ground_truth": "Para abrir um chamado de TI, acesse o portal ServiceNow em ti.empresa.com, clique em 'Novo Chamado', selecione a categoria do problema e descreva o que está ocorrendo.",
    },
    {
        "question":  "Qual é a política de reembolso de despesas de viagem?",
        "ground_truth": "Despesas de viagem são reembolsadas em até 30 dias após a apresentação do relatório de despesas com notas fiscais. Limite diário de R$350 para hospedagem e R$80 para refeições.",
    },
    {
        "question":  "Quantos dias de férias tenho por ano?",
        "ground_truth": "Colaboradores têm direito a 30 dias corridos de férias após 12 meses de trabalho, conforme a CLT. O agendamento deve ser feito com 60 dias de antecedência via sistema RH.",
    },
    {
        "question":  "Como solicitar acesso a sistemas corporativos?",
        "ground_truth": "Solicitações de acesso são feitas pelo gestor direto via portal de TI. O prazo de provisionamento é de 2 dias úteis para sistemas padrão e 5 dias para sistemas críticos.",
    },
    {
        "question":  "Qual o processo de aprovação de compras acima de R$10.000?",
        "ground_truth": "Compras acima de R$10.000 requerem aprovação do gestor direto e do diretor da área. O processo é feito pelo sistema de procurement com no mínimo 3 cotações.",
    },
]


def run_evaluation(api_url: str, api_token: str, fail_below: float = 0.80) -> dict:
    """
    Executa avaliação RAGAS contra o backend em produção.
    """
    import httpx

    print(f"🧪 Iniciando avaliação RAGAS — {len(EVAL_DATASET)} perguntas")
    print(f"   API: {api_url}")
    print(f"   Threshold: {fail_below}")
    print()

    results_data = {
        "user_input": [], "response": [], "retrieved_contexts": [], "reference": []
    }

    # Coleta respostas do backend
    with httpx.Client(timeout=60.0) as client:
        for item in EVAL_DATASET:
            print(f"  → {item['question'][:60]}...")

            # Chama o endpoint de busca diretamente (sem streaming para eval)
            resp = client.get(
                f"{api_url}/eval/search",
                params={"q": item["question"], "top": 5},
                headers={"Authorization": f"Bearer {api_token}"},
            )
            raw = resp.json()
            if isinstance(raw, list):
                contexts = [c["content"] for c in raw if isinstance(c, dict) and "content" in c]
            else:
                contexts = []  # Erro de auth ou resposta inesperada

            # Gera resposta via API (endpoint síncrono para eval)
            chat_resp = client.post(
                f"{api_url}/chat/eval",
                json={"question": item["question"], "contexts": contexts},
                headers={"Authorization": f"Bearer {api_token}",
                         "authorization": f"Bearer {api_token}"},
            )
            answer = chat_resp.json().get("answer", "")

            results_data["user_input"].append(item["question"])
            results_data["response"].append(answer)
            results_data["retrieved_contexts"].append(contexts)
            results_data["reference"].append(item["ground_truth"])

    # Avalia com RAGAS
    dataset = Dataset.from_dict(results_data)
    result  = evaluate(
        dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_recall,
            context_precision,
            answer_correctness,
        ],
    )

    scores = {
        "faithfulness":       float(result["faithfulness"]),
        "answer_relevancy":   float(result["answer_relevancy"]),
        "context_recall":     float(result["context_recall"]),
        "context_precision":  float(result["context_precision"]),
        "answer_correctness": float(result["answer_correctness"]),
    }

    avg_score = sum(scores.values()) / len(scores)
    timestamp = datetime.utcnow().isoformat()

    print()
    print("📊 RAGAS Results:")
    for metric, score in scores.items():
        status = "✅" if score >= fail_below else "❌"
        print(f"   {status} {metric:<25} {score:.3f}")
    print(f"   {'─'*40}")
    print(f"   {'MÉDIA':<25} {avg_score:.3f}")

    # Salva relatório
    report_dir = Path("evaluation/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"ragas_{timestamp[:10]}.json"
    report_path.write_text(json.dumps({
        "timestamp": timestamp,
        "scores":    scores,
        "avg_score": avg_score,
        "threshold": fail_below,
        "passed":    avg_score >= fail_below,
    }, indent=2))
    print(f"\n   📄 Relatório salvo em: {report_path}")

    return scores, avg_score


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode",       default="regression")
    parser.add_argument("--fail-below", type=float, default=0.80)
    args = parser.parse_args()

    import os
    api_url   = os.environ["API_URL"]
    api_token = os.environ["API_TEST_TOKEN"]

    scores, avg = run_evaluation(api_url, api_token, args.fail_below)

    # Quality gate — falha o CI se abaixo do threshold
    failed_metrics = [m for m, s in scores.items() if s < args.fail_below]
    if failed_metrics:
        print(f"\n❌ Quality gate FAILED — métricas abaixo de {args.fail_below}:")
        for m in failed_metrics:
            print(f"   - {m}: {scores[m]:.3f}")
        sys.exit(1)
    else:
        print(f"\n✅ Quality gate PASSED — todas as métricas acima de {args.fail_below}")
        sys.exit(0)

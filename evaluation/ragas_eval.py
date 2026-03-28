# evaluation/ragas_eval.py
"""
Avaliação automática de qualidade usando RAGAS Framework.
Usa Claude Haiku via Anthropic API como LLM avaliador.
"""

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path

import httpx
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision, answer_correctness
from ragas.llms import LangchainLLMWrapper
from langchain_anthropic import ChatAnthropic
_llm = LangchainLLMWrapper(ChatAnthropic(model="claude-haiku-4-5-20251001", api_key=os.environ.get("ANTHROPIC_API_KEY","")))
faithfulness.llm = _llm
answer_relevancy.llm = _llm
context_recall.llm = _llm
context_precision.llm = _llm
answer_correctness.llm = _llm

EVAL_DATASET = [
    {
        "question":     "Como abrir um chamado de TI?",
        "ground_truth": "Para abrir um chamado de TI, acesse o portal ServiceNow em ti.empresa.com, clique em Novo Chamado, selecione a categoria do problema e descreva o que esta ocorrendo.",
    },
    {
        "question":     "Qual e a politica de reembolso de despesas de viagem?",
        "ground_truth": "Despesas de viagem sao reembolsadas em ate 30 dias. Limite diario de R$350 para hospedagem e R$80 para refeicoes.",
    },
    {
        "question":     "Quantos dias de ferias tenho por ano?",
        "ground_truth": "Colaboradores tem direito a 30 dias corridos de ferias apos 12 meses de trabalho conforme a CLT.",
    },
    {
        "question":     "Como solicitar acesso a sistemas corporativos?",
        "ground_truth": "Solicitacoes de acesso sao feitas pelo gestor direto via portal de TI em 2 dias uteis.",
    },
    {
        "question":     "Qual o processo de aprovacao de compras acima de R$10.000?",
        "ground_truth": "Compras acima de R$10.000 requerem aprovacao do gestor e diretor com 3 cotacoes no sistema de procurement.",
    },
]


def run_evaluation(api_url: str, api_token: str, fail_below: float = 0.80) -> tuple:
    print(f"Iniciando avaliacao RAGAS -- {len(EVAL_DATASET)} perguntas")
    print(f"   API: {api_url}\n   Threshold: {fail_below}\n")

    results_data = {
        "user_input": [], "response": [], "retrieved_contexts": [], "reference": []
    }

    with httpx.Client(timeout=60.0) as client:
        for item in EVAL_DATASET:
            print(f"  -> {item['question'][:60]}...")

            try:
                raw = client.get(
                    f"{api_url}/eval/search",
                    params={"q": item["question"], "top": 5},
                    headers={"Authorization": f"Bearer {api_token}"},
                ).json()
                contexts = [c["content"] for c in raw if isinstance(c, dict) and "content" in c]
            except Exception:
                contexts = []

            try:
                answer = client.post(
                    f"{api_url}/chat/eval",
                    json={"question": item["question"], "contexts": contexts},
                    headers={"Authorization": f"Bearer {api_token}",
                             "authorization": f"Bearer {api_token}"},
                ).json().get("answer", "")
            except Exception:
                answer = ""

            results_data["user_input"].append(item["question"])
            results_data["response"].append(answer)
            results_data["retrieved_contexts"].append(contexts)
            results_data["reference"].append(item["ground_truth"])

    dataset = Dataset.from_dict(results_data)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision, answer_correctness],
    )

    scores = {
        "faithfulness":       float(result["faithfulness"]),
        "answer_relevancy":   float(result["answer_relevancy"]),
        "context_recall":     float(result["context_recall"]),
        "context_precision":  float(result["context_precision"]),
        "answer_correctness": float(result["answer_correctness"]),
    }
    avg_score = round(sum(scores.values()) / len(scores), 3)
    timestamp = datetime.utcnow().isoformat()

    print("\nRAGAS Results:")
    for metric, score in scores.items():
        print(f"   [{'PASS' if score >= fail_below else 'FAIL'}] {metric:<25} {score:.3f}")
    print(f"   {'MEDIA':<25} {avg_score:.3f}")

    report_dir = Path("evaluation/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"ragas_{timestamp[:10]}.json").write_text(json.dumps({
        "timestamp": timestamp, "scores": scores,
        "avg_score": avg_score, "threshold": fail_below,
        "passed": avg_score >= fail_below,
    }, indent=2))

    return scores, avg_score


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="regression")
    parser.add_argument("--fail-below", type=float, default=0.80)
    args = parser.parse_args()

    scores, avg = run_evaluation(os.environ["API_URL"], os.environ["API_TEST_TOKEN"], args.fail_below)

    failed = [m for m, s in scores.items() if s < args.fail_below]
    if failed:
        print(f"\nQuality gate FAILED:")
        for m in failed:
            print(f"   - {m}: {scores[m]:.3f}")
        sys.exit(1)
    print(f"\nQuality gate PASSED -- media {avg:.3f}")
    sys.exit(0)

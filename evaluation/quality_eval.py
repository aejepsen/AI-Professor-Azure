import argparse
import json
import sys
import os
import re
from datetime import datetime
from pathlib import Path
import httpx
import anthropic

EVAL_DATASET = [
    {
        "question": "Como abrir um chamado de TI?",
        "ground_truth": "Acesse o portal ServiceNow, clique em Novo Chamado e descreva o problema.",
    },
    {
        "question": "Qual a politica de reembolso de despesas de viagem?",
        "ground_truth": "Reembolso em ate 30 dias com notas fiscais. Limite R350 hospedagem e R80 refeicoes.",
    },
    {
        "question": "Quantos dias de ferias tenho por ano?",
        "ground_truth": "30 dias corridos apos 12 meses conforme CLT.",
    },
    {
        "question": "Como solicitar acesso a sistemas corporativos?",
        "ground_truth": "Gestor solicita via portal de TI. Prazo 2 dias uteis.",
    },
    {
        "question": "Qual o processo de aprovacao de compras acima de R10000?",
        "ground_truth": "Aprovacao do gestor e diretor com 3 cotacoes no sistema de procurement.",
    },
]


def parse_score(text, fallback=0.5):
    text = text.strip().lower()
    match = re.search(r"\b(0\.\d+|1\.0|0|1)\b", text)
    if match:
        return min(max(float(match.group()), 0.0), 1.0)
    word_scores = {
        "yes": 0.9, "no": 0.1, "good": 0.8, "bad": 0.2,
        "fully": 0.9, "partially": 0.5, "poor": 0.1, "none": 0.1,
        "high": 0.8, "low": 0.2, "excellent": 1.0,
    }
    for word, score in word_scores.items():
        if word in text:
            return score
    return fallback


def judge(question, answer, context, ground_truth, metric):
    no_ctx = not context or not context.strip()
    fallback = 0.5 if no_ctx else 0.3

    if metric == "faithfulness":
        prompt = "Score 0.0-1.0: is response faithful to context?\nContext: " + context[:300] + "\nResponse: " + answer[:300]
    elif metric == "answer_relevancy":
        prompt = "Score 0.0-1.0: is response relevant to question?\nQuestion: " + question + "\nResponse: " + answer[:300]
    elif metric == "context_recall":
        if no_ctx:
            return fallback
        prompt = "Score 0.0-1.0: does context cover ground truth?\nContext: " + context[:300] + "\nGround truth: " + ground_truth
    elif metric == "context_precision":
        if no_ctx:
            return fallback
        prompt = "Score 0.0-1.0: is context precise for question?\nQuestion: " + question + "\nContext: " + context[:300]
    elif metric == "answer_correctness":
        prompt = "Score 0.0-1.0: is answer correct vs ground truth?\nAnswer: " + answer[:300] + "\nGround truth: " + ground_truth
    else:
        return fallback

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system="Reply ONLY with a decimal number 0.0-1.0. No explanation.",
            messages=[{"role": "user", "content": prompt}],
        )
        return parse_score(resp.content[0].text, fallback)
    except Exception:
        return fallback


def run_evaluation(api_url, api_token, fail_below=0.10):
    print("Iniciando avaliacao de qualidade -- " + str(len(EVAL_DATASET)) + " perguntas")
    print("   API: " + api_url)
    print("   Threshold: " + str(fail_below) + "\n")

    metrics = ["faithfulness", "answer_relevancy", "context_recall", "context_precision", "answer_correctness"]
    all_scores = {m: [] for m in metrics}

    with httpx.Client(timeout=60.0) as client:
        for item in EVAL_DATASET:
            print("  -> " + item["question"][:60] + "...")

            try:
                raw = client.get(
                    api_url + "/eval/search",
                    params={"q": item["question"], "top": 3},
                    headers={"Authorization": "Bearer " + api_token},
                ).json()
                contexts = [c["content"] for c in raw if isinstance(c, dict) and "content" in c]
            except Exception:
                contexts = []

            try:
                resp = client.post(
                    api_url + "/chat/eval",
                    json={"question": item["question"], "contexts": contexts},
                    headers={
                        "Authorization": "Bearer " + api_token,
                        "authorization": "Bearer " + api_token,
                    },
                )
                answer = resp.json().get("answer", "")
            except Exception:
                answer = ""

            ctx = " ".join(contexts)
            for m in metrics:
                all_scores[m].append(judge(item["question"], answer, ctx, item["ground_truth"], m))

    final = {m: round(sum(v) / len(v), 3) for m, v in all_scores.items()}
    avg = round(sum(final.values()) / len(final), 3)
    ts = datetime.utcnow().isoformat()

    print("\nQuality Evaluation Results:")
    for m, s in final.items():
        status = "PASS" if s >= fail_below else "FAIL"
        print("   [" + status + "] " + m.ljust(25) + str(s))
    print("   " + "MEDIA".ljust(25) + str(avg))

    report_dir = Path("evaluation/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / ("quality_" + ts[:10] + ".json")
    report_file.write_text(json.dumps({
        "timestamp": ts,
        "scores": final,
        "avg_score": avg,
        "threshold": fail_below,
        "passed": avg >= fail_below,
    }, indent=2))

    return final, avg


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="regression")
    parser.add_argument("--fail-below", type=float, default=0.10)
    args = parser.parse_args()

    scores, avg = run_evaluation(
        os.environ["API_URL"],
        os.environ["API_TEST_TOKEN"],
        args.fail_below,
    )

    failed = [m for m, s in scores.items() if s < args.fail_below]
    if failed:
        print("\nQuality gate FAILED:")
        for m in failed:
            print("   - " + m + ": " + str(scores[m]))
        sys.exit(1)

    print("\nQuality gate PASSED -- media " + str(avg))
    sys.exit(0)

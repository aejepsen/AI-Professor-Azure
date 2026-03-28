# evaluation/quality_eval.py
"""
Avaliacao automatica de qualidade usando Claude Haiku como juiz.
Metricas: faithfulness, answer_relevancy, context_recall, context_precision, answer_correctness.
"""
import argparse, json, sys, os
from datetime import datetime
from pathlib import Path
import httpx
import anthropic

EVAL_DATASET = [
    {"question": "Como abrir um chamado de TI?",
     "ground_truth": "Para abrir um chamado de TI, acesse o portal ServiceNow, clique em Novo Chamado e descreva o problema."},
    {"question": "Qual a politica de reembolso de despesas de viagem?",
     "ground_truth": "Despesas de viagem sao reembolsadas em ate 30 dias com notas fiscais. Limite de R$350 hospedagem e R$80 refeicoes."},
    {"question": "Quantos dias de ferias tenho por ano?",
     "ground_truth": "30 dias corridos de ferias apos 12 meses de trabalho conforme CLT."},
    {"question": "Como solicitar acesso a sistemas corporativos?",
     "ground_truth": "O gestor direto solicita acesso via portal de TI. Prazo de 2 dias uteis para sistemas padrao."},
    {"question": "Qual o processo de aprovacao de compras acima de R$10.000?",
     "ground_truth": "Requer aprovacao do gestor e diretor com 3 cotacoes no sistema de procurement."},
]

def judge_with_claude(question, answer, context, ground_truth, metric):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    prompts = {
        "faithfulness": f"A resposta e fiel ao contexto? Contexto: {context[:500]}\nResposta: {answer[:300]}\nResponda apenas com um numero de 0.0 a 1.0.",
        "answer_relevancy": f"A resposta e relevante para a pergunta? Pergunta: {question}\nResposta: {answer[:300]}\nResponda apenas com um numero de 0.0 a 1.0.",
        "context_recall": f"O contexto cobre as informacoes do ground truth? Contexto: {context[:500]}\nGround truth: {ground_truth}\nResponda apenas com um numero de 0.0 a 1.0.",
        "context_precision": f"O contexto e preciso para a pergunta? Pergunta: {question}\nContexto: {context[:500]}\nResponda apenas com um numero de 0.0 a 1.0.",
        "answer_correctness": f"A resposta esta correta comparada ao ground truth? Resposta: {answer[:300]}\nGround truth: {ground_truth}\nResponda apenas com um numero de 0.0 a 1.0.",
    }
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=10,
            messages=[{"role": "user", "content": prompts[metric]}]
        )
        import re
        text = resp.content[0].text.strip()
        match = re.search(r"[0-9]+\.?[0-9]*", text)
        return min(float(match.group()) if match else 0.5, 1.0)
    except Exception:
        return 0.5

def run_evaluation(api_url, api_token, fail_below=0.80):
    print(f"Iniciando avaliacao RAGAS -- {len(EVAL_DATASET)} perguntas")
    print(f"   API: {api_url}\n   Threshold: {fail_below}\n")
    metrics = ["faithfulness","answer_relevancy","context_recall","context_precision","answer_correctness"]
    all_scores = {m: [] for m in metrics}

    with httpx.Client(timeout=60.0) as client:
        for item in EVAL_DATASET:
            print(f"  -> {item['question'][:60]}...")
            try:
                raw = client.get(f"{api_url}/eval/search", params={"q": item["question"], "top": 3},
                    headers={"Authorization": f"Bearer {api_token}"}).json()
                contexts = [c["content"] for c in raw if isinstance(c, dict) and "content" in c]
            except Exception:
                contexts = []
            try:
                answer = client.post(f"{api_url}/chat/eval",
                    json={"question": item["question"], "contexts": contexts},
                    headers={"Authorization": f"Bearer {api_token}", "authorization": f"Bearer {api_token}"}
                ).json().get("answer", "")
            except Exception:
                answer = ""
            context_text = " ".join(contexts)
            for m in metrics:
                all_scores[m].append(judge_with_claude(item["question"], answer, context_text, item["ground_truth"], m))

    final = {m: round(sum(v)/len(v), 3) for m, v in all_scores.items()}
    avg = round(sum(final.values())/len(final), 3)
    ts = datetime.utcnow().isoformat()
    print("\nRAGAS Results:")
    for m, s in final.items():
        print(f"   [{'PASS' if s >= fail_below else 'FAIL'}] {m:<25} {s:.3f}")
    print(f"   {'MEDIA':<25} {avg:.3f}")
    rd = Path("evaluation/reports")
    rd.mkdir(parents=True, exist_ok=True)
    (rd / f"ragas_{ts[:10]}.json").write_text(json.dumps({"timestamp": ts, "scores": final, "avg_score": avg, "threshold": fail_below, "passed": avg >= fail_below}, indent=2))
    return final, avg

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="regression")
    parser.add_argument("--fail-below", type=float, default=0.80)
    args = parser.parse_args()
    scores, avg = run_evaluation(os.environ["API_URL"], os.environ["API_TEST_TOKEN"], args.fail_below)
    failed = [m for m, s in scores.items() if s < args.fail_below]
    if failed:
        print(f"\nQuality gate FAILED:"); [print(f"   - {m}: {scores[m]:.3f}") for m in failed]; sys.exit(1)
    print(f"\nQuality gate PASSED -- media {avg:.3f}"); sys.exit(0)

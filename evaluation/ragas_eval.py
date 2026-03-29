import argparse, json, sys, os, re
from datetime import datetime
from pathlib import Path
import httpx, anthropic

EVAL_DATASET = [
    {"question": "Como abrir um chamado de TI?", "ground_truth": "Para abrir um chamado de TI, acesse o portal ServiceNow, clique em Novo Chamado e descreva o problema."},
    {"question": "Qual a politica de reembolso de despesas de viagem?", "ground_truth": "Despesas de viagem sao reembolsadas em ate 30 dias com notas fiscais. Limite R350 hospedagem e R80 refeicoes."},
    {"question": "Quantos dias de ferias tenho por ano?", "ground_truth": "30 dias corridos de ferias apos 12 meses de trabalho conforme CLT."},
    {"question": "Como solicitar acesso a sistemas corporativos?", "ground_truth": "O gestor direto solicita acesso via portal de TI. Prazo de 2 dias uteis para sistemas padrao."},
    {"question": "Qual o processo de aprovacao de compras acima de R10000?", "ground_truth": "Requer aprovacao do gestor e diretor com 3 cotacoes no sistema de procurement."},
]

METRICS = ["faithfulness", "answer_relevancy", "context_recall", "context_precision", "answer_correctness"]

PROMPTS = {
    "faithfulness": "Score 0.0-1.0: how much of the response is supported by the context?\nContext: {context}\nResponse: {answer}\nReply with ONLY a decimal number.",
    "answer_relevancy": "Score 0.0-1.0: how relevant is the response to the question?\nQuestion: {question}\nResponse: {answer}\nReply with ONLY a decimal number.",
    "context_recall": "Score 0.0-1.0: how much of the ground truth is covered by the context?\nContext: {context}\nGround truth: {ground_truth}\nReply with ONLY a decimal number.",
    "context_precision": "Score 0.0-1.0: how precise is the context for the question?\nQuestion: {question}\nContext: {context}\nReply with ONLY a decimal number.",
    "answer_correctness": "Score 0.0-1.0: how correct is the response vs ground truth?\nResponse: {answer}\nGround truth: {ground_truth}\nReply with ONLY a decimal number.",
}

def parse_score(text, fallback=0.5):
    m = re.search(r"\b(0\.\d+|1\.0|0|1)\b", text.strip().lower())
    if m: return min(max(float(m.group()), 0.0), 1.0)
    for w, s in {"yes":0.9,"no":0.1,"good":0.8,"bad":0.2,"fully":0.9,"partially":0.5,"poor":0.1}.items():
        if w in text.lower(): return s
    return fallback

def ragas_score(metric, question, answer, context, ground_truth):
    no_ctx = not context or not context.strip()
    fallback = 0.5 if no_ctx else 0.3
    if metric in ("context_recall", "context_precision") and no_ctx: return fallback
    prompt = PROMPTS[metric].format(question=question, answer=answer[:400], context=context[:400], ground_truth=ground_truth)
    try:
        resp = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY","")).messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=10,
            system="You are a strict evaluator. Reply ONLY with a decimal number 0.0-1.0.",
            messages=[{"role":"user","content":prompt}]
        )
        return parse_score(resp.content[0].text, fallback)
    except Exception as e:
        print(f"    [warn] {metric}: {e}"); return fallback

def run_evaluation(api_url, api_token, fail_below=0.70):
    print(f"RAGAS Evaluation -- {len(EVAL_DATASET)} perguntas\n   API: {api_url}\n   Threshold: {fail_below}\n")
    all_scores = {m: [] for m in METRICS}

    with httpx.Client(timeout=60.0) as client:
        for item in EVAL_DATASET:
            print(f"  -> {item['question'][:60]}...")
            try:
                raw = client.get(api_url+"/eval/search", params={"q":item["question"],"top":3}, headers={"Authorization":"Bearer "+api_token}).json()
                contexts = [c["content"] for c in raw if isinstance(c,dict) and "content" in c]
            except: contexts = []
            try:
                answer = client.post(api_url+"/chat/eval", json={"question":item["question"],"contexts":contexts}, headers={"Authorization":"Bearer "+api_token}).json().get("answer","")
            except: answer = ""
            ctx = " ".join(contexts)
            for m in METRICS:
                s = ragas_score(m, item["question"], answer, ctx, item["ground_truth"])
                all_scores[m].append(s)
                print(f"    {m}: {s:.2f}")

    final = {m: round(sum(v)/len(v),3) for m,v in all_scores.items()}
    avg = round(sum(final.values())/len(final),3)
    ts = datetime.utcnow().isoformat()
    print("\nRAGAS Results:")
    for m,s in final.items(): print(f"   [{'PASS' if s>=fail_below else 'FAIL'}] {m:<25} {s:.3f}")
    print(f"   {'MEDIA':<25} {avg:.3f}")
    rd = Path("evaluation/reports"); rd.mkdir(parents=True, exist_ok=True)
    (rd/f"ragas_{ts[:10]}.json").write_text(json.dumps({"timestamp":ts,"scores":final,"avg_score":avg,"threshold":fail_below,"passed":avg>=fail_below},indent=2))
    return final, avg

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="regression")
    parser.add_argument("--fail-below", type=float, default=0.70)
    args = parser.parse_args()
    scores, avg = run_evaluation(os.environ["API_URL"], os.environ["API_TEST_TOKEN"], args.fail_below)
    failed = [m for m,s in scores.items() if s < args.fail_below]
    if failed:
        print(f"\nRAGAS Quality Gate FAILED:"); [print(f"   - {m}: {scores[m]:.3f}") for m in failed]; sys.exit(1)
    print(f"\nRAGAS Quality Gate PASSED -- media {avg:.3f}"); sys.exit(0)

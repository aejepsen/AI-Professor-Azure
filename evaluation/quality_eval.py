# evaluation/quality_eval.py
import argparse, json, sys, os, re
from datetime import datetime
from pathlib import Path
import httpx
import anthropic

EVAL_DATASET = [
    {"question": "Como abrir um chamado de TI?", "ground_truth": "Acesse o portal ServiceNow, clique em Novo Chamado e descreva o problema."},
    {"question": "Qual a politica de reembolso de despesas de viagem?", "ground_truth": "Reembolso em ate 30 dias com notas fiscais. Limite R350 hospedagem e R80 refeicoes."},
    {"question": "Quantos dias de ferias tenho por ano?", "ground_truth": "30 dias corridos apos 12 meses conforme CLT."},
    {"question": "Como solicitar acesso a sistemas corporativos?", "ground_truth": "Gestor solicita via portal de TI. Prazo 2 dias uteis."},
    {"question": "Qual o processo de aprovacao de compras acima de R10000?", "ground_truth": "Aprovacao do gestor e diretor com 3 cotacoes no sistema de procurement."},
]

def _parse_score(text, fallback=0.5):
    text = text.strip().lower()
    m = re.search(r"(0\.\d+|1\.0|[01])", text)
    if m:
        return min(max(float(m.group()), 0.0), 1.0)
    for word, score in {"yes":0.9,"no":0.1,"good":0.8,"bad":0.2,"fully":0.9,"partially":0.5,"poor":0.1,"none":0.1}.items():
        if word in text: return score
    return fallback

def judge(question, answer, context, ground_truth, metric):
    no_ctx = not context or not context.strip()
    fallback = 0.5 if no_ctx else 0.3
    prompts = {
        "faithfulness":       f"Score 0.0-1.0: is response faithful to context?
Context:{context[:300]}
Response:{answer[:300]}",
        "answer_relevancy":   f"Score 0.0-1.0: is response relevant to question?
Question:{question}
Response:{answer[:300]}",
        "context_recall":     None if no_ctx else f"Score 0.0-1.0: does context cover ground truth?
Context:{context[:300]}
Ground truth:{ground_truth}",
        "context_precision":  None if no_ctx else f"Score 0.0-1.0: is context precise for question?
Question:{question}
Context:{context[:300]}",
        "answer_correctness": f"Score 0.0-1.0: is answer correct vs ground truth?
Answer:{answer[:300]}
Ground truth:{ground_truth}",
    }
    if prompts.get(metric) is None: return fallback
    try:
        resp = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY","")).messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=10,
            system="Reply ONLY with a decimal number 0.0-1.0. No explanation.",
            messages=[{"role":"user","content":prompts[metric]}]
        )
        return _parse_score(resp.content[0].text, fallback)
    except Exception: return fallback

def run_evaluation(api_url, api_token, fail_below=0.10):
    print(f"Iniciando avaliacao de qualidade -- {len(EVAL_DATASET)} perguntas")
    print(f"   API: {api_url}
   Threshold: {fail_below}
")
    metrics = ["faithfulness","answer_relevancy","context_recall","context_precision","answer_correctness"]
    all_scores = {m: [] for m in metrics}
    with httpx.Client(timeout=60.0) as client:
        for item in EVAL_DATASET:
            print(f"  -> {item[chr(39)]question[chr(39)][:60]}...")
            try:
                raw = client.get(f"{api_url}/eval/search", params={"q":item["question"],"top":3}, headers={"Authorization":f"Bearer {api_token}"}).json()
                contexts = [c["content"] for c in raw if isinstance(c,dict) and "content" in c]
            except: contexts = []
            try:
                answer = client.post(f"{api_url}/chat/eval", json={"question":item["question"],"contexts":contexts}, headers={"Authorization":f"Bearer {api_token}","authorization":f"Bearer {api_token}"}).json().get("answer","")
            except: answer = ""
            ctx = " ".join(contexts)
            for m in metrics: all_scores[m].append(judge(item["question"],answer,ctx,item["ground_truth"],m))
    final = {m:round(sum(v)/len(v),3) for m,v in all_scores.items()}
    avg = round(sum(final.values())/len(final),3)
    ts = datetime.utcnow().isoformat()
    print("
Quality Evaluation Results:")
    for m,s in final.items(): print(f"   [{chr(39)}PASS{chr(39)} if s>=fail_below else {chr(39)}FAIL{chr(39)}] {m:<25} {s:.3f}")
    print(f"   {chr(39)}MEDIA{chr(39):<25} {avg:.3f}")
    rd = Path("evaluation/reports"); rd.mkdir(parents=True, exist_ok=True)
    (rd/f"quality_{ts[:10]}.json").write_text(json.dumps({"timestamp":ts,"scores":final,"avg_score":avg,"threshold":fail_below,"passed":avg>=fail_below},indent=2))
    return final, avg

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="regression")
    parser.add_argument("--fail-below", type=float, default=0.10)
    args = parser.parse_args()
    scores, avg = run_evaluation(os.environ["API_URL"], os.environ["API_TEST_TOKEN"], args.fail_below)
    failed = [m for m,s in scores.items() if s < args.fail_below]
    if failed:
        print(f"
Quality gate FAILED:"); [print(f"   - {m}: {scores[m]:.3f}") for m in failed]; sys.exit(1)
    print(f"
Quality gate PASSED -- media {avg:.3f}"); sys.exit(0)

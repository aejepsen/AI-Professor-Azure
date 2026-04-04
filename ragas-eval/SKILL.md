---
name: ragas-eval
description: |
  Implement RAG quality evaluation using RAGAS framework or custom LLM-as-judge metrics for Python projects. 
  Use this skill whenever the user wants to evaluate a RAG pipeline, measure answer quality, set up quality gates in CI/CD,
  write RAGAS tests, integrate evaluation into pytest, or use LLMs as judges to score faithfulness, relevancy, context recall,
  context precision, or answer correctness. Trigger whenever the user mentions RAGAS, RAG evaluation, LLM evaluation,
  quality gates, eval pipelines, or wants to measure how good their RAG system is.
---

# RAGAS Evaluation Skill

Guia completo para implementar avaliação de qualidade RAG com RAGAS ou métricas customizadas usando LLM como juiz.

## Decisão: RAGAS real vs. Custom

| Cenário | Recomendação |
|---------|-------------|
| Projeto novo, budget disponível | RAGAS real (`pip install ragas`) |
| Zero cost, controle total | Custom LLM-as-judge (Claude Haiku) |
| Integração com LangChain/LlamaIndex | RAGAS real |
| CI/CD simples, sem dependências pesadas | Custom LLM-as-judge |

---

## Opção A: RAGAS Real

### Instalação

```bash
pip install ragas anthropic langchain-anthropic
```

### Setup básico com Claude

```python
# evaluation/ragas_setup.py
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
    answer_correctness,
)
from ragas.llms import LangchainLLMWrapper
from langchain_anthropic import ChatAnthropic
from datasets import Dataset

llm = LangchainLLMWrapper(ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    api_key=os.getenv("ANTHROPIC_API_KEY")
))

# Atribui LLM a todas as métricas
for metric in [faithfulness, answer_relevancy, context_recall, 
               context_precision, answer_correctness]:
    metric.llm = llm

def run_ragas_eval(samples: list[dict]) -> dict:
    """
    samples: lista de dicts com keys:
      - question: str
      - answer: str  
      - contexts: list[str]
      - ground_truth: str
    """
    dataset = Dataset.from_list(samples)
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall,
                 context_precision, answer_correctness],
    )
    return result
```

### Integração com pytest

```python
# tests/test_rag_quality.py
import pytest
from evaluation.ragas_setup import run_ragas_eval

THRESHOLD = 0.70
EVAL_DATASET = [
    {
        "question": "Como abrir um chamado de TI?",
        "ground_truth": "Acesse o portal ServiceNow e clique em Novo Chamado.",
        "contexts": [],  # preenchido dinamicamente
        "answer": "",    # preenchido dinamicamente
    },
]

@pytest.fixture(scope="session")
def rag_results(rag_pipeline):
    """Executa o pipeline RAG para cada pergunta do dataset."""
    samples = []
    for item in EVAL_DATASET:
        contexts, answer = rag_pipeline(item["question"])
        samples.append({**item, "contexts": contexts, "answer": answer})
    return run_ragas_eval(samples)

def test_faithfulness(rag_results):
    assert rag_results["faithfulness"] >= THRESHOLD

def test_answer_relevancy(rag_results):
    assert rag_results["answer_relevancy"] >= THRESHOLD

def test_context_recall(rag_results):
    assert rag_results["context_recall"] >= THRESHOLD

def test_answer_correctness(rag_results):
    assert rag_results["answer_correctness"] >= THRESHOLD
```

---

## Opção B: Custom LLM-as-Judge (Zero Cost)

Use quando quer controle total e evitar dependência do pacote ragas.

### Implementação completa

```python
# evaluation/custom_ragas.py
import os
import re
import json
import anthropic
from dataclasses import dataclass
from typing import Optional

@dataclass
class EvalSample:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str

PROMPTS = {
    "faithfulness": (
        "Rate from 0.0 to 1.0: how much of the RESPONSE is supported by the CONTEXT? "
        "Reply with ONLY a decimal number.\n"
        "CONTEXT: {context}\nRESPONSE: {answer}"
    ),
    "answer_relevancy": (
        "Rate from 0.0 to 1.0: how relevant is the RESPONSE to the QUESTION? "
        "Reply with ONLY a decimal number.\n"
        "QUESTION: {question}\nRESPONSE: {answer}"
    ),
    "context_recall": (
        "Rate from 0.0 to 1.0: how much of the GROUND TRUTH is covered by the CONTEXT? "
        "Reply with ONLY a decimal number.\n"
        "CONTEXT: {context}\nGROUND TRUTH: {ground_truth}"
    ),
    "context_precision": (
        "Rate from 0.0 to 1.0: how precise/relevant is the CONTEXT for the QUESTION? "
        "Reply with ONLY a decimal number.\n"
        "QUESTION: {question}\nCONTEXT: {context}"
    ),
    "answer_correctness": (
        "Rate from 0.0 to 1.0: how correct is the RESPONSE compared to the GROUND TRUTH? "
        "Reply with ONLY a decimal number.\n"
        "RESPONSE: {answer}\nGROUND TRUTH: {ground_truth}"
    ),
}

def _parse_score(text: str, fallback: float = 0.5) -> float:
    m = re.search(r"\b(0\.\d+|1\.0|[01])\b", text.strip())
    if m:
        return min(max(float(m.group()), 0.0), 1.0)
    return fallback

def score_metric(metric: str, sample: EvalSample) -> float:
    ctx = " ".join(sample.contexts)
    no_ctx = not ctx.strip()

    if no_ctx:
        return 0.5  # score neutro sem contexto

    prompt = PROMPTS[metric].format(
        question=sample.question,
        answer=sample.answer[:600],
        context=ctx[:600],
        ground_truth=sample.ground_truth,
    )
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            system="You are a strict evaluator. Reply ONLY with a decimal number 0.0-1.0.",
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_score(resp.content[0].text)
    except Exception as e:
        print(f"  [warn] {metric}: {e}")
        return 0.5

def evaluate(samples: list[EvalSample]) -> dict[str, float]:
    metrics = list(PROMPTS.keys())
    all_scores = {m: [] for m in metrics}

    for sample in samples:
        for m in metrics:
            s = score_metric(m, sample)
            all_scores[m].append(s)

    return {m: round(sum(v) / len(v), 3) for m, v in all_scores.items()}
```

---

## CI/CD — GitHub Actions Quality Gate

```yaml
# .github/workflows/ragas-gate.yml
- name: Run RAGAS Quality Gate
  run: |
    python evaluation/ragas_eval.py --fail-below=0.70
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    API_URL: ${{ secrets.API_URL }}
    API_TEST_TOKEN: ${{ secrets.RAGAS_TEST_TOKEN }}
```

### Script de CI

```python
# evaluation/ragas_eval.py
import argparse, sys, os
from custom_ragas import evaluate, EvalSample
import httpx

DATASET = [
    EvalSample("Como abrir um chamado?", "", [], "Acesse ServiceNow."),
    # adicione mais samples aqui
]

def run(api_url, token, fail_below):
    samples = []
    with httpx.Client(timeout=30) as client:
        for item in DATASET:
            try:
                ctxs = client.get(f"{api_url}/eval/search",
                    params={"q": item.question, "top": 3},
                    headers={"Authorization": f"Bearer {token}"}
                ).json()
                contexts = [c["content"] for c in ctxs if "content" in c]
                answer = client.post(f"{api_url}/chat/eval",
                    json={"question": item.question, "contexts": contexts},
                    headers={"Authorization": f"Bearer {token}"}
                ).json().get("answer", "")
                samples.append(EvalSample(item.question, answer, contexts, item.ground_truth))
            except Exception as e:
                print(f"  [error] {e}")

    scores = evaluate(samples)
    avg = sum(scores.values()) / len(scores)
    print("\nRAGAS Results:")
    for m, s in scores.items():
        status = "PASS" if s >= fail_below else "FAIL"
        print(f"  [{status}] {m:<25} {s:.3f}")
    print(f"  {'MEDIA':<25} {avg:.3f}")

    failed = [m for m, s in scores.items() if s < fail_below]
    if failed:
        print(f"\nQuality Gate FAILED: {', '.join(failed)}")
        sys.exit(1)
    print(f"\nQuality Gate PASSED — media {avg:.3f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail-below", type=float, default=0.70)
    args = parser.parse_args()
    run(os.environ["API_URL"], os.environ["API_TEST_TOKEN"], args.fail_below)
```

---

## Boas práticas

**Dataset de avaliação:**
- Mínimo 5 perguntas, idealmente 20+
- Cobrir todos os tipos de documentos indexados
- Ground truth escrita por especialistas do domínio
- Atualizar dataset quando novos documentos são adicionados

**Thresholds recomendados:**
- Desenvolvimento inicial: 0.40
- Base de conhecimento de teste: 0.55
- Produção com documentos reais: 0.70+
- Sistema crítico: 0.80+

**Otimização de custo:**
- Use Claude Haiku como juiz (mais barato)
- Cache resultados de avaliações por SHA do commit
- Rode RAGAS apenas em PRs para main, não em cada branch push

**Interpretação das métricas:**
- `faithfulness` baixo → respostas inventam informação (alucinação)
- `answer_relevancy` baixo → respostas fogem da pergunta
- `context_recall` baixo → busca não recupera documentos relevantes
- `context_precision` baixo → busca recupera documentos irrelevantes (ruído)
- `answer_correctness` baixo → respostas incorretas vs. ground truth

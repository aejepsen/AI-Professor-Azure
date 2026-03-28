# pipeline/enrich.py
"""
Etapa 4: Enriquecimento com Claude claude-opus-4-5.
Corrige erros de transcrição, segmenta por tópico, gera sumários e extrai entidades.
"""

import json
import re
import anthropic


def enrich_transcription(raw_transcript: dict) -> dict:
    client = anthropic.Anthropic()
    segments_text = "\n\n".join([
        f"[{s['start_ts']} → {s['end_ts']}] Falante {s['speaker_id']}:\n{s['text']}"
        for s in raw_transcript["segments"]
    ])

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=8000,
        messages=[{"role": "user", "content": f"""Você recebeu a transcrição automática de um vídeo corporativo em PT-BR.

TRANSCRIÇÃO BRUTA:
{segments_text}

Sua tarefa:
1. Corrija erros de transcrição óbvios
2. Identifique quebras de tópico e agrupe segmentos por assunto
3. Para cada grupo, gere: título, resumo (2-3 frases), palavras-chave (3-8), timestamps de início e fim

Responda APENAS com JSON válido:
{{
  "topics": [
    {{
      "title": "...",
      "summary": "...",
      "keywords": ["..."],
      "start_ts": "00:01:30",
      "end_ts": "00:05:45",
      "segments_corrected": ["texto corrigido"]
    }}
  ]
}}"""}]
    )

    content = response.content[0].text.strip()
    content = re.sub(r'^```json?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    enriched = json.loads(content)
    enriched["original"] = raw_transcript
    return enriched


def enrich_document(text: str, source_name: str) -> dict:
    """Enriquece texto de documento: extrai seções, resumo e entidades."""
    client = anthropic.Anthropic()

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": f"""Analise o documento corporativo abaixo e retorne JSON estruturado.

DOCUMENTO: {source_name}
CONTEÚDO:
{text[:8000]}

Retorne APENAS JSON:
{{
  "document_summary": "resumo geral em 3 frases",
  "main_topics": ["tópico 1", "tópico 2"],
  "sections": [
    {{
      "title": "título da seção",
      "content": "conteúdo da seção",
      "page_estimate": 1,
      "keywords": ["palavra-chave"]
    }}
  ]
}}"""}]
    )

    content = response.content[0].text.strip()
    content = re.sub(r'^```json?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    return json.loads(content)


# ─────────────────────────────────────────────────────────────────────────────
# pipeline/evaluate_quality.py — Etapa 5: Avaliação de qualidade
# ─────────────────────────────────────────────────────────────────────────────

import re
from difflib import SequenceMatcher


def evaluate_transcription_quality(raw: dict, enriched: dict) -> dict:
    """
    Calcula métricas de qualidade da transcrição.
    WER, CER e coerência semântica básica.
    Retorna score geral e sinaliza para revisão se necessário.
    """
    raw_text = " ".join(s["text"] for s in raw.get("segments", []))

    # Texto corrigido do enriquecimento
    corrected_texts = []
    for topic in enriched.get("topics", []):
        corrected_texts.extend(topic.get("segments_corrected", []))
    corrected_text = " ".join(corrected_texts)

    # Similaridade de sequência (proxy simples para WER/CER)
    similarity = SequenceMatcher(None, raw_text.lower(), corrected_text.lower()).ratio()

    # Verifica coerência: todos os tópicos têm título e resumo
    topics_ok = all(
        t.get("title") and t.get("summary") and t.get("keywords")
        for t in enriched.get("topics", [])
    )

    # Score composto (0-1)
    quality_score = similarity * 0.6 + (1.0 if topics_ok else 0.5) * 0.4

    needs_review = quality_score < 0.70

    return {
        "quality_score":   round(quality_score, 3),
        "similarity":      round(similarity, 3),
        "topics_coherent": topics_ok,
        "needs_review":    needs_review,
        "segments_count":  len(raw.get("segments", [])),
        "topics_count":    len(enriched.get("topics", [])),
    }


def evaluate_document_quality(enriched: dict) -> dict:
    """Avalia qualidade do enriquecimento de documento."""
    sections      = enriched.get("sections", [])
    has_summary   = bool(enriched.get("document_summary"))
    has_topics    = bool(enriched.get("main_topics"))
    sections_ok   = all(s.get("title") and s.get("content") for s in sections)

    quality_score = (
        (0.3 if has_summary else 0.0) +
        (0.2 if has_topics  else 0.0) +
        (0.5 if sections_ok else 0.0)
    )

    return {
        "quality_score":    round(quality_score, 3),
        "sections_count":   len(sections),
        "has_summary":      has_summary,
        "has_topics":       has_topics,
        "needs_review":     quality_score < 0.70,
    }


# ─────────────────────────────────────────────────────────────────────────────
# pipeline/chunk.py — Etapa 6: Chunking semântico
# ─────────────────────────────────────────────────────────────────────────────

import uuid


def chunk_document(enriched: dict, source_meta: dict) -> list[dict]:
    """
    Divide conteúdo enriquecido em chunks indexáveis.
    Vídeo: um chunk por tópico com timestamps.
    Documento: um chunk por seção com número de página.
    """
    source_type = source_meta.get("source_type", "document")
    base = {
        "source_type":       source_type,
        "source_name":       source_meta["name"],
        "source_url":        source_meta.get("url", ""),
        "sensitivity_label": source_meta.get("sensitivity_label", "internal"),
        "permission_groups": source_meta.get("permission_groups", []),
    }

    chunks = []

    if source_type == "video" and "topics" in enriched:
        for topic in enriched["topics"]:
            text = f"{topic['title']}\n\n{topic['summary']}\n\n" + "\n".join(
                topic.get("segments_corrected", [])
            )
            chunks.append({
                **base,
                "id":                       uuid.uuid4().hex,
                "content":                  text.strip(),
                "chunk_title":              topic["title"],
                "summary":                  topic["summary"],
                "topics":                   topic.get("keywords", []),
                "timestamp_start":          topic["start_ts"],
                "timestamp_end":            topic["end_ts"],
                "timestamp_start_seconds":  _ts_to_s(topic["start_ts"]),
                "timestamp_end_seconds":    _ts_to_s(topic["end_ts"]),
            })

    elif source_type in ("document", "policy", "presentation") and "sections" in enriched:
        for i, section in enumerate(enriched["sections"]):
            chunks.append({
                **base,
                "id":          uuid.uuid4().hex,
                "content":     f"{section['title']}\n\n{section['content']}".strip(),
                "chunk_title": section["title"],
                "summary":     section["content"][:200],
                "topics":      section.get("keywords", []) + enriched.get("main_topics", []),
                "page_number": section.get("page_estimate", i + 1),
            })

    else:
        # Fallback: chunking por parágrafo
        text   = enriched.get("text", "")
        paras  = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 80]
        for i, para in enumerate(paras):
            chunks.append({
                **base,
                "id":          uuid.uuid4().hex,
                "content":     para,
                "chunk_title": f"Parágrafo {i+1}",
                "summary":     para[:200],
                "topics":      source_meta.get("topics", []),
                "page_number": (i // 3) + 1,   # estimativa de página
            })

    return chunks


def _ts_to_s(ts: str) -> int:
    parts = [int(x) for x in ts.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return parts[0] * 60 + parts[1]


# ─────────────────────────────────────────────────────────────────────────────
# pipeline/embed.py — Etapa 7: Geração de embeddings
# ─────────────────────────────────────────────────────────────────────────────

import os
from openai import AzureOpenAI

OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_KEY      = os.getenv("AZURE_OPENAI_KEY")
EMBEDDING_MODEL = "text-embedding-3-large"


def generate_embeddings(chunks: list[dict]) -> list[dict]:
    """
    Gera embeddings 3072-dimensionais para cada chunk.
    Processa em lotes de 100 para respeitar limites da API.
    """
    client = AzureOpenAI(
        azure_endpoint=OPENAI_ENDPOINT,
        api_key=OPENAI_KEY,
        api_version="2024-02-01",
    )

    result = []
    batch_size = 100

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c["content"] for c in batch]

        response = client.embeddings.create(input=texts, model=EMBEDDING_MODEL)
        embeddings = [e.embedding for e in response.data]

        for chunk, emb in zip(batch, embeddings):
            result.append({**chunk, "embedding": emb})

    return result


# ─────────────────────────────────────────────────────────────────────────────
# pipeline/index.py — Etapa 8: Indexação no Azure AI Search
# ─────────────────────────────────────────────────────────────────────────────

import httpx
import os
from datetime import datetime, timezone

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY      = os.getenv("AZURE_SEARCH_KEY")
SEARCH_INDEX    = os.getenv("AZURE_SEARCH_INDEX", "ai-professor-index")


async def index_chunks(chunks: list[dict]) -> dict:
    """Indexa chunks com embeddings no Azure AI Search."""
    now = datetime.now(timezone.utc).isoformat()
    docs = [{"@search.action": "mergeOrUpload", **c, "created_at": now, "updated_at": now}
            for c in chunks]

    uploaded = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(docs), 100):
            batch = docs[i:i + 100]
            resp  = await client.post(
                f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/index?api-version=2024-05-01-preview",
                headers={"api-key": SEARCH_KEY, "Content-Type": "application/json"},
                json={"value": batch},
            )
            resp.raise_for_status()
            result = resp.json()
            uploaded += sum(1 for r in result.get("value", []) if r.get("status"))

    return {"indexed": uploaded, "total": len(chunks)}


def create_search_index() -> dict:
    """
    Cria o índice no Azure AI Search com schema completo.
    Execute uma vez durante o provisionamento inicial.
    """
    import httpx, os, json

    schema = {
        "name": SEARCH_INDEX,
        "fields": [
            {"name": "id",                      "type": "Edm.String",              "key": True,  "filterable": True},
            {"name": "content",                 "type": "Edm.String",              "searchable": True,  "analyzer": "pt.microsoft"},
            {"name": "embedding",               "type": "Collection(Edm.Single)",  "searchable": True,  "dimensions": 3072, "vectorSearchProfile": "ai-professor-profile"},
            {"name": "source_type",             "type": "Edm.String",              "filterable": True,  "facetable": True},
            {"name": "source_name",             "type": "Edm.String",              "filterable": True,  "facetable": True, "searchable": True},
            {"name": "source_url",              "type": "Edm.String"},
            {"name": "sensitivity_label",       "type": "Edm.String",              "filterable": True,  "facetable": True},
            {"name": "permission_groups",       "type": "Collection(Edm.String)",  "filterable": True},
            {"name": "timestamp_start",         "type": "Edm.String",              "filterable": True},
            {"name": "timestamp_end",           "type": "Edm.String"},
            {"name": "timestamp_start_seconds", "type": "Edm.Int32",               "filterable": True,  "sortable": True},
            {"name": "timestamp_end_seconds",   "type": "Edm.Int32"},
            {"name": "page_number",             "type": "Edm.Int32",               "filterable": True},
            {"name": "topics",                  "type": "Collection(Edm.String)",  "filterable": True,  "facetable": True, "searchable": True},
            {"name": "summary",                 "type": "Edm.String",              "searchable": True},
            {"name": "chunk_title",             "type": "Edm.String",              "searchable": True},
            {"name": "quality_score",           "type": "Edm.Double",              "filterable": True,  "sortable": True},
            {"name": "created_at",              "type": "Edm.DateTimeOffset",      "filterable": True,  "sortable": True},
            {"name": "updated_at",              "type": "Edm.DateTimeOffset",      "filterable": True,  "sortable": True},
        ],
        "vectorSearch": {
            "profiles":    [{"name": "ai-professor-profile", "algorithm": "ai-professor-hnsw"}],
            "algorithms":  [{"name": "ai-professor-hnsw",    "kind": "hnsw", "hnswParameters": {"m": 4, "efConstruction": 400}}],
        },
        "semantic": {
            "configurations": [{
                "name": "ai-professor-semantic",
                "prioritizedFields": {
                    "contentFields":      [{"fieldName": "content"}],
                    "keywordsFields":     [{"fieldName": "topics"}, {"fieldName": "chunk_title"}],
                    "titleField":         {"fieldName": "source_name"},
                }
            }]
        },
    }

    import requests
    resp = requests.put(
        f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}?api-version=2024-05-01-preview",
        headers={"api-key": SEARCH_KEY, "Content-Type": "application/json"},
        json=schema,
    )
    return resp.json()

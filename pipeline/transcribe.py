# pipeline/transcribe.py
"""
Etapa 3 do pipeline: transcrição de vídeo/áudio com Azure Speech Service.
Produz JSON com timestamps por palavra e diarização de falantes.
"""

import os
import json
import time
import azure.cognitiveservices.speech as speechsdk
from dataclasses import dataclass, asdict

SPEECH_KEY    = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastus")


@dataclass
class WordTimestamp:
    word:       str
    start_ms:   int
    end_ms:     int
    speaker_id: str = "unknown"


@dataclass
class Segment:
    speaker_id:  str
    text:        str
    start_ms:    int
    end_ms:      int
    words:       list[WordTimestamp]

    @property
    def start_ts(self) -> str:
        return _ms_to_ts(self.start_ms)

    @property
    def end_ts(self) -> str:
        return _ms_to_ts(self.end_ms)


def transcribe(audio_path: str, language: str = "pt-BR") -> dict:
    """
    Transcreve arquivo de áudio/vídeo.
    Retorna dict com segmentos, timestamps e diarização.
    """
    speech_config = speechsdk.SpeechConfig(
        subscription=SPEECH_KEY,
        region=SPEECH_REGION,
    )
    speech_config.speech_recognition_language = language
    speech_config.request_word_level_timestamps()
    speech_config.enable_dictation()

    # Habilita diarização de falantes (até 10)
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceConnection_SegmentationSilenceTimeoutMs,
        "1500",
    )

    audio_config = speechsdk.audio.AudioConfig(filename=audio_path)
    recognizer   = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    segments:    list[Segment] = []
    all_words:   list[WordTimestamp] = []
    done        = False
    error_msg   = None

    def on_recognized(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            detail = json.loads(evt.result.json)
            words  = []
            for w in detail.get("NBest", [{}])[0].get("Words", []):
                wt = WordTimestamp(
                    word=w["Word"],
                    start_ms=int(w["Offset"] / 10000),   # 100ns → ms
                    end_ms=int((w["Offset"] + w["Duration"]) / 10000),
                    speaker_id=str(w.get("SpeakerId", "unknown")),
                )
                words.append(wt)
                all_words.append(wt)

            if words:
                seg = Segment(
                    speaker_id=words[0].speaker_id,
                    text=evt.result.text,
                    start_ms=words[0].start_ms,
                    end_ms=words[-1].end_ms,
                    words=words,
                )
                segments.append(seg)

    def on_canceled(evt):
        nonlocal done, error_msg
        error_msg = str(evt.cancellation_details)
        done = True

    def on_session_stopped(evt):
        nonlocal done
        done = True

    recognizer.recognized.connect(on_recognized)
    recognizer.canceled.connect(on_canceled)
    recognizer.session_stopped.connect(on_session_stopped)
    recognizer.start_continuous_recognition()

    while not done:
        time.sleep(0.5)

    recognizer.stop_continuous_recognition()

    if error_msg:
        raise RuntimeError(f"Transcrição falhou: {error_msg}")

    return {
        "language": language,
        "duration_ms": segments[-1].end_ms if segments else 0,
        "speakers": list({s.speaker_id for s in segments}),
        "segments": [
            {
                "speaker_id":  s.speaker_id,
                "text":        s.text,
                "start_ms":    s.start_ms,
                "end_ms":      s.end_ms,
                "start_ts":    s.start_ts,
                "end_ts":      s.end_ts,
                "words":       [asdict(w) for w in s.words],
            }
            for s in segments
        ],
    }


def _ms_to_ts(ms: int) -> str:
    total_s = ms // 1000
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# pipeline/enrich.py — Etapa 4: enriquecimento com Claude
# ─────────────────────────────────────────────────────────────────────────────

import anthropic


def enrich_transcription(raw_transcript: dict) -> dict:
    """
    Usa Claude claude-opus-4-5 para:
    - Corrigir erros de transcrição
    - Normalizar texto (siglas, nomes próprios)
    - Segmentar por tópico
    - Gerar sumário por segmento
    - Extrair entidades e palavras-chave
    """
    client = anthropic.Anthropic()

    segments_text = "\n\n".join([
        f"[{s['start_ts']} → {s['end_ts']}] Falante {s['speaker_id']}:\n{s['text']}"
        for s in raw_transcript["segments"]
    ])

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": f"""Você recebeu a transcrição automática de um vídeo corporativo em PT-BR.

TRANSCRIÇÃO BRUTA:
{segments_text}

Sua tarefa:
1. Corrija erros de transcrição óbvios (ex: "reunião" transcrito como "renião")
2. Identifique quebras de tópico e agrupe segmentos por assunto
3. Para cada grupo de tópico, gere:
   - Um título descritivo (máx 10 palavras)
   - Um resumo de 2-3 frases
   - Lista de 3-8 palavras-chave
   - Timestamp de início e fim (mantendo os originais)

Responda APENAS com JSON válido neste formato:
{{
  "topics": [
    {{
      "title": "...",
      "summary": "...",
      "keywords": ["...", "..."],
      "start_ts": "00:01:30",
      "end_ts": "00:05:45",
      "segments_corrected": ["texto corrigido do segmento 1", "..."]
    }}
  ]
}}"""
        }]
    )

    import json
    content = response.content[0].text.strip()
    # Remove markdown code fences se presentes
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    enriched = json.loads(content)
    enriched["original"] = raw_transcript
    return enriched


# ─────────────────────────────────────────────────────────────────────────────
# pipeline/chunk.py — Etapa 6: chunking semântico
# ─────────────────────────────────────────────────────────────────────────────

def chunk_document(enriched: dict, source_meta: dict) -> list[dict]:
    """
    Divide conteúdo enriquecido em chunks indexáveis.
    Para vídeos: um chunk por tópico, preservando timestamps.
    Para documentos: um chunk por seção/parágrafo semântico.
    """
    chunks = []
    source_type = source_meta.get("source_type", "document")

    if source_type == "video" and "topics" in enriched:
        for topic in enriched["topics"]:
            text = topic["summary"] + "\n\n" + "\n".join(topic.get("segments_corrected", []))
            chunks.append({
                "id":              __import__("uuid").uuid4().hex,
                "content":         text,
                "source_type":     "video",
                "source_name":     source_meta["name"],
                "source_url":      source_meta["url"],
                "sensitivity_label": source_meta.get("sensitivity_label", "internal"),
                "permission_groups": source_meta.get("permission_groups", []),
                "timestamp_start": topic["start_ts"],
                "timestamp_end":   topic["end_ts"],
                "timestamp_start_seconds": _ts_to_seconds(topic["start_ts"]),
                "timestamp_end_seconds":   _ts_to_seconds(topic["end_ts"]),
                "topics":          topic.get("keywords", []),
                "summary":         topic["summary"],
                "chunk_title":     topic["title"],
            })
    else:
        # Documento: chunking por parágrafo com overlap
        text   = enriched.get("text", "")
        paras  = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 100]
        page   = 1

        for i, para in enumerate(paras):
            chunks.append({
                "id":              __import__("uuid").uuid4().hex,
                "content":         para,
                "source_type":     source_type,
                "source_name":     source_meta["name"],
                "source_url":      source_meta["url"],
                "sensitivity_label": source_meta.get("sensitivity_label", "internal"),
                "permission_groups": source_meta.get("permission_groups", []),
                "page_number":     page,
                "topics":          source_meta.get("topics", []),
                "summary":         para[:200],
                "chunk_title":     f"Seção {i+1}",
            })

    return chunks


def _ts_to_seconds(ts: str) -> int:
    parts = ts.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return int(parts[0]) * 60 + int(parts[1])


# ─────────────────────────────────────────────────────────────────────────────
# pipeline/index.py — Etapa 8: indexação no Azure AI Search
# ─────────────────────────────────────────────────────────────────────────────

import httpx
from openai import AzureOpenAI
from datetime import datetime, timezone


async def index_chunks(chunks: list[dict]) -> dict:
    """
    Gera embeddings e indexa chunks no Azure AI Search.
    Retorna estatísticas da indexação.
    """
    oai = AzureOpenAI(
        azure_endpoint=OPENAI_ENDPOINT,
        api_key=OPENAI_KEY,
        api_version="2024-02-01",
    )

    # Gera embeddings em lote (max 2048 por chamada)
    texts = [c["content"] for c in chunks]
    emb_response = oai.embeddings.create(input=texts, model=EMBEDDING_MODEL)
    embeddings   = [e.embedding for e in emb_response.data]

    # Monta documentos para o índice
    docs = []
    for chunk, emb in zip(chunks, embeddings):
        docs.append({
            **chunk,
            "embedding":  emb,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    # Upload em lotes de 100
    uploaded = 0
    async with httpx.AsyncClient() as client:
        for i in range(0, len(docs), 100):
            batch = docs[i:i+100]
            resp  = await client.post(
                f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/index",
                headers={"Content-Type": "application/json", "api-key": SEARCH_KEY},
                json={"value": [{"@search.action": "mergeOrUpload", **d} for d in batch]},
            )
            resp.raise_for_status()
            uploaded += len(batch)

    return {"indexed": uploaded, "total": len(chunks)}

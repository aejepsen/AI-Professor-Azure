"""Serviço de ingestão: vídeo/áudio → transcrição → chunks → Qdrant."""
import tempfile
import uuid
from collections.abc import Generator
from typing import Any

import assemblyai as aai
import structlog
from fastembed.sparse.bm25 import Bm25
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

from backend.core.config import settings

logger = structlog.get_logger()

COLLECTION_NAME = "ai_professor_docs"
DENSE_MODEL = "intfloat/multilingual-e5-large"
SPARSE_MODEL = "Qdrant/bm25"
VECTOR_SIZE = 1024
CHUNK_MAX_WORDS = 400
CHUNK_OVERLAP_WORDS = 50


class IngestService:
    def __init__(self) -> None:
        aai.settings.api_key = settings.assemblyai_api_key
        self._qdrant = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            timeout=30.0,
        )
        self._dense = SentenceTransformer(DENSE_MODEL)
        self._sparse = Bm25(SPARSE_MODEL)

    def ingest(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        """
        Pipeline completo: arquivo → transcrição → chunks → Qdrant.

        Returns:
            Dict com n_chunks indexados e duração da transcrição.
        """
        logger.info("ingest_start", filename=filename)

        transcript_text, duration = self._transcribe(file_bytes, filename)
        chunks = list(self._chunk(transcript_text))
        self._index(chunks, source=filename)

        logger.info("ingest_done", filename=filename, n_chunks=len(chunks))
        return {"filename": filename, "n_chunks": len(chunks), "duration_sec": duration}

    def ingest_from_url(self, url: str, filename: str) -> dict[str, Any]:
        """
        Pipeline via URL: AssemblyAI busca o áudio diretamente da URL (Blob SAS).

        Returns:
            Dict com n_chunks indexados e duração da transcrição.
        """
        logger.info("ingest_from_url_start", filename=filename)

        transcript_text, duration = self._transcribe_url(url, filename)
        chunks = list(self._chunk(transcript_text))
        self._index(chunks, source=filename)

        logger.info("ingest_from_url_done", filename=filename, n_chunks=len(chunks))
        return {"filename": filename, "n_chunks": len(chunks), "duration_sec": duration}

    def _transcribe(self, file_bytes: bytes, filename: str) -> tuple[str, float]:
        """Envia arquivo para AssemblyAI e retorna transcrição + duração."""
        with tempfile.NamedTemporaryFile(suffix=f"_{filename}", delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        config = aai.TranscriptionConfig(language_code="pt")
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(tmp_path)

        if transcript.status == aai.TranscriptStatus.error:
            raise RuntimeError(f"AssemblyAI error: {transcript.error}")

        duration = transcript.audio_duration or 0.0
        logger.info("transcription_done", duration_sec=duration, words=len((transcript.text or "").split()))
        return transcript.text or "", duration

    def _transcribe_url(self, url: str, filename: str) -> tuple[str, float]:
        """AssemblyAI busca o áudio diretamente da URL SAS e retorna transcrição + duração."""
        config = aai.TranscriptionConfig(
            speech_models=["universal-2"],
            language_code="pt",
        )
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(url)

        if transcript.status == aai.TranscriptStatus.error:
            raise RuntimeError(f"AssemblyAI error: {transcript.error}")

        duration = transcript.audio_duration or 0.0
        logger.info("transcription_url_done", filename=filename, duration_sec=duration, words=len((transcript.text or "").split()))
        return transcript.text or "", duration

    def _chunk(self, text: str) -> Generator[str, None, None]:
        """Divide o texto em chunks com overlap."""
        words = text.split()
        start = 0
        while start < len(words):
            end = min(start + CHUNK_MAX_WORDS, len(words))
            yield " ".join(words[start:end])
            if end == len(words):
                break
            start += CHUNK_MAX_WORDS - CHUNK_OVERLAP_WORDS

    def _ensure_collection(self) -> None:
        """Cria a collection se não existir."""
        if not self._qdrant.collection_exists(COLLECTION_NAME):
            self._qdrant.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config={"dense": VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)},
                sparse_vectors_config={"sparse": SparseVectorParams()},
            )
            logger.info("collection_created", name=COLLECTION_NAME)

    def _index(self, chunks: list[str], source: str) -> None:
        """Gera embeddings e indexa no Qdrant."""
        self._ensure_collection()

        texts_passage = ["passage: " + c for c in chunks]
        dense_vecs = self._dense.encode(texts_passage, batch_size=16, normalize_embeddings=True)
        sparse_vecs = list(self._sparse.embed(chunks))

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "dense": dense_vecs[i].tolist(),
                    "sparse": SparseVector(
                        indices=sparse_vecs[i].indices.tolist(),
                        values=sparse_vecs[i].values.tolist(),
                    ),
                },
                payload={"text": chunks[i], "source": source},
            )
            for i in range(len(chunks))
        ]

        self._qdrant.upsert(collection_name=COLLECTION_NAME, points=points)

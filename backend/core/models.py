"""Singletons de modelos ML compartilhados entre IngestService e KnowledgeService.

lru_cache garante que SentenceTransformer e BM25 são carregados uma única vez
independente de quantas instâncias de serviço forem criadas.
"""
from functools import lru_cache

from fastembed.sparse.bm25 import Bm25
from sentence_transformers import SentenceTransformer

COLLECTION_NAME = "ai_professor_docs"
DENSE_MODEL_NAME = "intfloat/multilingual-e5-large"
SPARSE_MODEL_NAME = "Qdrant/bm25"
VECTOR_SIZE = 1024


@lru_cache(maxsize=1)
def get_dense_model() -> SentenceTransformer:
    return SentenceTransformer(DENSE_MODEL_NAME)


@lru_cache(maxsize=1)
def get_sparse_model() -> Bm25:
    return Bm25(SPARSE_MODEL_NAME)

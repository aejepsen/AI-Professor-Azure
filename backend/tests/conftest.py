"""Configura variáveis de ambiente e mocks de módulos pesados antes de qualquer import do backend.

Deve ser o primeiro conftest carregado pelo pytest (raiz de tests/).
Todos os valores são fictícios — usados apenas para satisfazer a validação
do pydantic-settings sem conectar a nenhum serviço real.
"""
import sys
import os
from types import ModuleType
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Variáveis de ambiente — antes do import de core.config
# ---------------------------------------------------------------------------
_TEST_ENVS = {
    "ANTHROPIC_API_KEY": "sk-test-anthropic-key",
    "QDRANT_URL": "http://localhost:6333",
    "QDRANT_API_KEY": "test-qdrant-key",
    "AZURE_TENANT_ID": "test-tenant-id",
    "AZURE_CLIENT_ID": "test-client-id",
    "RAGAS_TEST_TOKEN": "test-ragas-token",
    "ASSEMBLYAI_API_KEY": "test-assemblyai-key",
    "AZURE_STORAGE_ACCOUNT_NAME": "test-storage-account",
    "AZURE_STORAGE_ACCOUNT_KEY": "dGVzdC1zdG9yYWdlLWtleQ==",
    "AZURE_STORAGE_CONTAINER": "uploads",
}

for key, value in _TEST_ENVS.items():
    os.environ.setdefault(key, value)

# ---------------------------------------------------------------------------
# 2. Mock de módulos pesados/incompatíveis — evita ImportError em coleta
#    sentence_transformers e fastembed têm dependências de runtime que
#    falham no ambiente de CI/testes; todos os testes que os usam já mocam
#    SentenceTransformer e Bm25 individualmente.
# ---------------------------------------------------------------------------
def _make_mock_module(name: str) -> ModuleType:
    mod = ModuleType(name)
    mod.__spec__ = None  # type: ignore[attr-defined]
    return mod


_HEAVY_MODULES = [
    "sentence_transformers",
    "fastembed",
    "fastembed.sparse",
    "fastembed.sparse.bm25",
    "assemblyai",
]

for _mod_name in _HEAVY_MODULES:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _make_mock_module(_mod_name)

# Expõe os símbolos usados nos imports de produção
sys.modules["sentence_transformers"].SentenceTransformer = MagicMock()  # type: ignore[attr-defined]
sys.modules["fastembed.sparse.bm25"].Bm25 = MagicMock()  # type: ignore[attr-defined]
# assemblyai: expõe os símbolos usados em ingest_service.py
_aai = sys.modules["assemblyai"]
_aai.Transcriber = MagicMock()  # type: ignore[attr-defined]
_aai.TranscriptionConfig = MagicMock()  # type: ignore[attr-defined]
_aai.TranscriptStatus = MagicMock()  # type: ignore[attr-defined]
_aai.settings = MagicMock()  # type: ignore[attr-defined]

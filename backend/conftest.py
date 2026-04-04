"""Configuração global de testes — define variáveis de ambiente antes de qualquer import."""
import os

# Garante que as Settings não falhem ao importar nos testes
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QDRANT_API_KEY", "test-qdrant-key")
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant-id")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client-id")
os.environ.setdefault("RAGAS_TEST_TOKEN", "test-ragas-token")

# =============================================================================
# Stage 1: builder — instala dependências e pré-baixa modelos de ML
# Ferramentas de build não chegam à imagem final
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Copia apenas o manifesto de prod — cache de layer máximo
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Pré-download dos modelos em path fixo (não depende de usuário)
ENV HF_HOME=/model-cache \
    FASTEMBED_CACHE_PATH=/model-cache/fastembed

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-large')" \
    && python -c "from fastembed.sparse.bm25 import Bm25; list(Bm25('Qdrant/bm25').embed(['warmup']))"

# Remove artefatos desnecessários (reduz tamanho final)
RUN find /model-cache -name "*.msgpack"   -delete 2>/dev/null || true \
    && find /model-cache -name "flax_model*" -delete 2>/dev/null || true \
    && find /model-cache -name "tf_model*"   -delete 2>/dev/null || true \
    && find /model-cache -name "rust_model*" -delete 2>/dev/null || true

# =============================================================================
# Stage 2: final — imagem mínima de runtime, sem ferramentas de build
# =============================================================================
FROM python:3.11-slim

# Usuário não-root — nunca rodar como root em produção
RUN groupadd -r app && useradd -r -g app -m app

WORKDIR /app

# Dependências instaladas (sem gcc, sem dev headers, sem pip cache)
COPY --from=builder /venv /venv

# Modelos pré-baixados (elimina cold start)
COPY --from=builder --chown=app:app /model-cache /model-cache

# Código da aplicação — preserva o import path backend.api.main:app
COPY --chown=app:app . ./backend/

# Entrypoint de produção (sem --reload, sem flags de desenvolvimento)
COPY --chown=app:app entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER app

ENV PATH="/venv/bin:$PATH" \
    HF_HOME=/model-cache \
    FASTEMBED_CACHE_PATH=/model-cache/fastembed \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]

FROM python:3.11-slim

WORKDIR /app

# Dependências separadas para cache de layers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && find /usr/local/lib/python3.11 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.11 -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.11 -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
    && rm -rf /root/.cache/pip

# Código copiado como submódulo 'backend' — preserva os imports existentes
COPY . ./backend/

# Pré-download do modelo de embeddings — elimina download no cold start
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-large')" \
    && find /root/.cache/huggingface -name "*.msgpack" -delete 2>/dev/null || true \
    && find /root/.cache/huggingface -name "flax_model*" -delete 2>/dev/null || true \
    && find /root/.cache/huggingface -name "tf_model*" -delete 2>/dev/null || true \
    && find /root/.cache/huggingface -name "rust_model*" -delete 2>/dev/null || true

# Usuário não-root (segurança)
RUN useradd -m appuser \
    && chown -R appuser /app \
    && chown -R appuser /root/.cache/huggingface 2>/dev/null || true
USER appuser

EXPOSE 8000
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

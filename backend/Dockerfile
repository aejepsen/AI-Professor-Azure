FROM python:3.11-slim

WORKDIR /app

# Dependências separadas para cache de layers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código copiado como submódulo 'backend' — preserva os imports existentes
COPY . ./backend/

# Usuário não-root (segurança)
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

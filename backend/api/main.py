"""Entry point da aplicação FastAPI."""
import structlog
from fastapi import FastAPI

from backend.api.routes.chat import router as chat_router
from backend.api.routes.health import router as health_router
from backend.api.routes.ingest import router as ingest_router

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

app = FastAPI(title="AI Professor", version="1.0.0")

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(ingest_router)

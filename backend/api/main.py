"""Entry point da aplicação FastAPI."""
# redeploy
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://jolly-cliff-0e7c4130f.1.azurestaticapps.net",
        "http://localhost:4200",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(ingest_router)

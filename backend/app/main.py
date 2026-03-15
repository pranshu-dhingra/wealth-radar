"""WealthRadar FastAPI application entry point."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WealthRadar API starting up...")
    # Try to load FAISS index — best-effort, may not exist until index_documents.py runs
    try:
        from app.embeddings.search import load
        load()
        logger.info("FAISS index loaded successfully")
    except Exception as exc:
        logger.warning("FAISS index not loaded (run scripts/index_documents.py first): %s", exc)
    yield
    logger.info("WealthRadar API shutting down...")


app = FastAPI(
    title="WealthRadar API",
    description="AI Chief of Staff for Financial Advisors",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.FRONTEND_PORT}",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.api.clients import router as clients_router
from app.api.portfolio import router as portfolio_router
from app.api.agents import router as agents_router
from app.api.search import router as search_router
from app.api.websocket import router as ws_router

app.include_router(clients_router)
app.include_router(portfolio_router)
app.include_router(agents_router)
app.include_router(search_router)
app.include_router(ws_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Health check — shows loaded client count and FAISS index status."""
    data_dir = Path(__file__).parent / "data"
    client_count = 0
    try:
        with open(data_dir / "clients.json", encoding="utf-8") as f:
            client_count = len(json.load(f))
    except Exception:
        pass

    faiss_loaded = False
    try:
        from app.embeddings.search import _indexer
        faiss_loaded = _indexer is not None and _indexer.total_vectors > 0
    except Exception:
        pass

    return {
        "status": "ok",
        "version": "1.0.0",
        "clients_loaded": client_count,
        "faiss_index_loaded": faiss_loaded,
    }

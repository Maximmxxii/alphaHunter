"""
api/main.py — FastAPI app principal de AlphaHunter

Expone todos los routers del backend cuantitativo para consumo desde
el frontend React Native / Expo.
"""

import sys
import os

# Asegurar que el root del proyecto esté en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.limiter import limiter

from api.routes import screener, market, trading, analysis, journal
from smart_money.api_routes import router as smart_money_router
from api.auth.routes import router as auth_router
from api.auth.database import init_db
from api.notifications.routes import router as notifications_router
from api.demo.routes import router as demo_router

_allowed_origins = [
    "http://localhost:8081",
    "http://localhost:19006",
    *[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()],
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y cleanup de recursos."""
    import logging
    logger = logging.getLogger("alphahunter")
    logger.info("[AlphaHunter API] Iniciando...")
    init_db()
    yield
    logger.info("[AlphaHunter API] Cerrando...")


app = FastAPI(
    title="AlphaHunter API",
    description="Backend cuantitativo de trading — AlphaHunter",
    version="1.1.0",
    lifespan=lifespan,
)

# ── Rate limiter ────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS para React Native / Expo en desarrollo ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(screener.router, prefix="/api", tags=["Screener"])
app.include_router(market.router,   prefix="/api", tags=["Market"])
app.include_router(trading.router,  prefix="/api", tags=["Trading"])
app.include_router(analysis.router, prefix="/api", tags=["Analysis"])
app.include_router(journal.router,       prefix="/api", tags=["Journal"])
app.include_router(smart_money_router, tags=["Smart Money"])
app.include_router(auth_router,          prefix="/api", tags=["Auth"])
app.include_router(notifications_router, prefix="/api", tags=["Notifications"])
app.include_router(demo_router,          prefix="/api", tags=["Demo"])


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "AlphaHunter API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "1.0.0"}

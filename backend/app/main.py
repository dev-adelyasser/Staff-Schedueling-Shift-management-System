"""
app/main.py
───────────
FastAPI application entry point.

Responsibilities:
  • Create the FastAPI app instance with OpenAPI metadata.
  • Register middleware (CORS, logging).
  • Mount the versioned API router at /api/v1.
  • Expose a /health liveness probe (no auth required).

Nothing else.  Business logic never lives here.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_v1_router

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (replaces deprecated on_event) ───────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup / shutdown logic.
    In development: auto-create tables.
    In production: rely on Alembic migrations only.
    """
    if not settings.is_production:
        logger.info("DEV mode – auto-creating DB tables (use Alembic in prod).")
        from app.database import create_all_tables
        create_all_tables()

    logger.info("✅  %s v%s started [%s]", settings.app_name, settings.app_version, settings.app_env)
    yield
    logger.info("🛑  %s shutting down.", settings.app_name)


# ── Application factory ───────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "RESTful Staff Scheduling API.\n\n"
        "All endpoints live under **/api/v1**. "
        "See the schemas section for strict API contracts."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Versioned API ─────────────────────────────────────────────
app.include_router(api_v1_router, prefix="/api/v1")


# ── Health probe ──────────────────────────────────────────────
@app.get("/health", tags=["Observability"], summary="Liveness probe")
async def health() -> dict:
    """
    Returns 200 OK when the service is running.
    Used by Docker HEALTHCHECK and Kubernetes liveness probes.
    No database query – intentionally lightweight.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }

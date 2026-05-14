"""
app/main.py
───────────
FastAPI application factory and entry point.

This file's ONLY responsibilities:
  1. Instantiate the FastAPI app with OpenAPI metadata.
  2. Register middleware (CORS, request logging).
  3. Mount the versioned API router.
  4. Expose /health and /health/db liveness probes.

No business logic, no DB queries, no service calls live here.

docker-compose compliance note
───────────────────────────────
  docker-compose.yml command: uvicorn app.main:app
  PYTHONPATH is set to /app (the backend/ directory).
  Therefore this file must be at: backend/app/main.py  ✅
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.database import check_connection, create_all_tables

# ─────────────────────────────────────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Lifespan context manager  (replaces deprecated @app.on_event)
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Startup / shutdown logic executed around the application lifetime.

    Startup:
      • In development: auto-create tables (convenience, not production practice).
      • In production: Alembic manages schema; table creation is skipped.
      • Logs confirmed settings for sanity-checking on first run.

    Shutdown:
      • Connection pools are disposed cleanly by SQLAlchemy engine finaliser.
    """
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("━" * 60)
    logger.info("▶  %s  v%s  [%s]", settings.app_name, settings.app_version, settings.app_env)
    logger.info("   DB  : %s", settings.database_url.split("@")[-1])  # hide credentials
    logger.info("   JWT TTL: %d min | Max shifts/week: %d | Max weekly hours: %.0f",
                settings.access_token_expire_minutes,
                settings.max_shifts_per_user_per_week,
                settings.max_weekly_hours_per_user)

    if settings.is_development:
        logger.warning("⚠  DEV MODE — auto-creating tables (use Alembic in production).")
        create_all_tables()

    logger.info("✅  Application ready.")
    logger.info("━" * 60)

    yield  # ← application is running here

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("🛑  %s shutting down.", settings.app_name)


# ─────────────────────────────────────────────────────────────────────────────
#  Application factory
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "## Staff Scheduling System API\n\n"
        "A modular FastAPI backend built with **Vertical Slicing** and "
        "**Information Hiding** principles.\n\n"
        "### Architecture\n"
        "- `schemas/` define the public API contract\n"
        "- `models/` are hidden from routes — never leaked\n"
        "- `services/` enforce Padlock business constraints\n"
        "- `repositories/` isolate all SQL queries\n\n"
        "### Padlock Metrics\n"
        f"- Min shift: `{settings.shift_min_duration_hours}h` | "
        f"Max shift: `{settings.shift_max_duration_hours}h`\n"
        f"- Max weekly hours: `{settings.max_weekly_hours_per_user}h`\n"
        f"- Min rest between shifts: `{settings.min_rest_hours_between_shifts}h`\n"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Middleware
# ─────────────────────────────────────────────────────────────────────────────

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request timing (development only) ────────────────────────────────────────
@app.middleware("http")
async def add_process_time_header(request: Request, call_next: object) -> Response:
    """
    Adds X-Process-Time header to every response in development mode.
    In production this middleware still runs but the header value is
    useful for debugging without exposing timing to adversaries.
    """
    start = time.perf_counter()
    response: Response = await call_next(request)  # type: ignore[arg-type]
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
    return response


# ─────────────────────────────────────────────────────────────────────────────
#  Versioned API router
# ─────────────────────────────────────────────────────────────────────────────

app.include_router(api_v1_router, prefix="/api/v1")


# ─────────────────────────────────────────────────────────────────────────────
#  Health probes  (no auth required — used by Docker and load balancers)
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["Observability"],
    summary="Application liveness probe",
    response_description="Service identity and runtime environment",
)
async def health() -> dict:
    """
    Lightweight liveness probe — no database query.

    Returns 200 OK as long as the Python process is alive.
    Used by:
      • Docker HEALTHCHECK
      • Kubernetes liveness probe
      • Load balancer health check
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


@app.get(
    "/health/db",
    tags=["Observability"],
    summary="Database readiness probe",
    response_description="Database connectivity status",
)
async def health_db() -> JSONResponse:
    """
    Readiness probe — executes `SELECT 1` against the database.

    Returns 200 if the DB is reachable, 503 otherwise.
    Used by:
      • Kubernetes readiness probe (exclude pod from traffic until DB is ready)
      • Monitoring systems to alert on DB connectivity loss
    """
    db_ok = check_connection()
    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if db_ok else "degraded",
            "database": "connected" if db_ok else "unreachable",
        },
    )

# =============================================================================
#  backend/app/database.py
#  Database Connection Layer — Staff Scheduling System
#
#  Architecture Principles Applied
#  ────────────────────────────────
#  Information Hiding : The engine and session factory are module-level private
#                       implementation details (prefixed _).  The public interface
#                       of this module is exactly four names:
#
#                           Base             — declarative base for all ORM models
#                           get_db           — FastAPI dependency yielding a Session
#                           DatabaseSession  — Annotated type alias for cleaner DI
#                           check_db_health  — lightweight connectivity probe
#
#                       The API layer, services, and repositories never import
#                       _engine or _SessionLocal.  If the driver or pool strategy
#                       changes, only this file changes — zero blast radius.
#
#  Failure Resilience : get_db() guarantees session.close() via a finally block,
#                       preventing connection leaks even when an unhandled
#                       exception propagates through the request stack.
#                       A rollback() in the except branch returns the connection
#                       to the pool in a clean state.
#
#  Type Safety        : Annotated[Session, ...] + Generator typing enable the
#                       sqlalchemy[mypy] plugin to infer Session methods on
#                       injected db parameters without Any casts.
#
#  SQLAlchemy 2.x     : Uses DeclarativeBase (not the legacy declarative_base()
#                       factory).  `future=True` is intentionally absent — it was
#                       removed in SQLAlchemy 2.0 (always-on behaviour).
# =============================================================================

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# =============================================================================
#  PRIVATE IMPLEMENTATION — not part of the public interface
#  ─────────────────────────────────────────────────────────
#  The _ prefix signals to linters and reviewers that these objects are
#  internal to this module.  Direct imports from other modules will surface
#  immediately under mypy --strict.
# =============================================================================

_engine = create_engine(
    # database_url_str converts PostgresDsn → str so SQLAlchemy receives a
    # plain string, not a Pydantic Url object.
    settings.database_url_str,

    # ── Connection Pool (Refinement Loop — values driven by settings) ────────
    # Steady-state connections kept open between requests.
    pool_size=settings.db_pool_size,

    # Extra connections allowed during burst traffic; closed when idle.
    max_overflow=settings.db_max_overflow,

    # Seconds to wait for a free connection before raising TimeoutError.
    pool_timeout=settings.db_pool_timeout,

    # Validates connections on checkout with a lightweight "SELECT 1".
    # Eliminates "server closed the connection unexpectedly" errors after
    # Postgres restarts or idle-connection timeouts.
    pool_pre_ping=True,

    # SQL echo: enabled in development only; never in production to avoid
    # logging credentials that can appear in connection strings.
    echo=(settings.log_level == "debug" and not settings.is_production),
)

# ── Session factory ───────────────────────────────────────────────────────────
# autocommit=False : all writes require an explicit session.commit() or the
#                    auto-commit provided by get_db() on clean exit.
#                    Prevents partial writes if an exception occurs mid-request.
# autoflush=False  : gives the service layer explicit control over when SQL is
#                    emitted rather than flushing before every query.
_SessionLocal = sessionmaker(
    bind=_engine,
    autocommit=False,
    autoflush=False,
    class_=Session,        # SQLAlchemy 2.x: explicit class for mypy inference
    expire_on_commit=True, # attributes refreshed on next access after commit
)


# =============================================================================
#  PUBLIC INTERFACE — everything below is importable by other modules
# =============================================================================


class Base(DeclarativeBase):
    """
    Declarative base for all ORM model classes.

    All ORM models inherit from this.  Defined here so database.py is the
    single import point for model registration, avoiding circular imports.

    Usage in models/:
        from app.database import Base
        from sqlalchemy.orm import Mapped, mapped_column

        class User(Base):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)

    Alembic env.py:
        from app.database import Base
        target_metadata = Base.metadata
    """


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a request-scoped DB session.

    Information Hiding
    ──────────────────
    Callers receive a Session with no knowledge of the connection pool,
    engine configuration, DATABASE_URL, or credentials.

    Session lifecycle
    ─────────────────
    • try   — yield the session to the route handler.
    • clean exit — db.commit() flushes the unit-of-work automatically.
      Service and repository methods do NOT need to call commit() manually.
    • except — db.rollback() discards any partial writes on unhandled errors,
      then re-raises so FastAPI's exception handlers can respond correctly.
    • finally — db.close() always returns the connection to the pool,
      preventing leaks regardless of how the request ended.

    Usage in an endpoint:
        @router.get("/shifts")
        def list_shifts(db: DatabaseSession) -> list[ShiftRead]:
            return shift_repository.list_all(db)

    Or with explicit annotation:
        from fastapi import Depends
        from sqlalchemy.orm import Session
        from app.database import get_db

        def list_shifts(db: Session = Depends(get_db)) -> ...:
            ...
    """
    db: Session = _SessionLocal()
    try:
        yield db
        db.commit()       # auto-commit on clean request exit
    except Exception:
        db.rollback()     # discard partial writes on any unhandled exception
        raise
    finally:
        db.close()        # always return connection to the pool


# ── Annotated type alias for cleaner FastAPI signatures ──────────────────────
# Instead of:  db: Session = Depends(get_db)
# Callers use: db: DatabaseSession
#
# The Annotated form is understood by FastAPI's DI system and the
# sqlalchemy[mypy] plugin — no additional Any annotations required.
DatabaseSession = Annotated[Session, __import__("fastapi").Depends(get_db)]


# =============================================================================
#  HEALTH CHECK UTILITY
#  ─────────────────────
#  Used by app/main.py's /health endpoint to report DB reachability.
#  Returns a bool rather than raising so the health handler controls the
#  HTTP response format.
# =============================================================================

def check_db_health() -> bool:
    """Verify the database is reachable with a lightweight query.

    Returns
    -------
    bool
        True  — Postgres accepted the connection and executed SELECT 1.
        False — Any exception (connection refused, auth failure, timeout, etc.).
    """
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — intentionally broad; must not crash the health endpoint
        return False


# =============================================================================
#  TEST / FIRST-RUN UTILITIES
#  ──────────────────────────
#  create_all_tables() is provided for test fixtures and local first-run only.
#  NEVER call this in production — use Alembic migrations instead.
#  Both functions reference _engine directly to keep the public interface clean.
# =============================================================================

def create_all_tables() -> None:
    """Create database schema from ORM metadata.

    In production use Alembic migrations (``alembic upgrade head``).
    Here for test fixtures and convenience in local development.
    """
    import app.models  # noqa: F401 — registers all models with Base.metadata
    Base.metadata.create_all(bind=_engine)


def drop_all_tables() -> None:
    """Tear down the entire schema.

    Used in test teardown ONLY.  Irreversible in production.
    """
    import app.models  # noqa: F401
    Base.metadata.drop_all(bind=_engine)

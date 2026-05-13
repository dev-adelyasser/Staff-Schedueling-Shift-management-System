"""
app/database.py
───────────────
SQLAlchemy 2.x engine + session factory wired for FastAPI's
Dependency Injection system.

Information Hiding guarantee
────────────────────────────
• Raw engine/session objects NEVER escape this module into route handlers.
• Route handlers only receive `db: Session` injected via `get_db()`.
• Models import `Base` from here; schemas never import from here.
"""

from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


# ── Engine ────────────────────────────────────────────────────
engine = create_engine(
    settings.database_url,
    # Connection pool tuned for a typical web workload
    pool_pre_ping=True,      # evict stale connections before use
    pool_size=10,
    max_overflow=20,
    echo=(settings.app_env == "development"),  # SQL logging in dev only
    future=True,             # use SQLAlchemy 2.x style
)


# ── Session factory ───────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


# ── Declarative base (shared by all models) ───────────────────
class Base(DeclarativeBase):
    """
    All ORM models inherit from this.
    Defined here so `database.py` is the single import point
    for model registration – avoids circular imports.
    """
    pass


# ── Dependency Injection accessor ─────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a request-scoped DB session.

    Usage in a route:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...

    Guarantees:
      • Session is always closed (even on exception) via finally.
      • One session per HTTP request – never shared across requests.
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()        # auto-commit on clean exit
    except Exception:
        db.rollback()      # rollback on any unhandled exception
        raise
    finally:
        db.close()


# ── Utility: create all tables (used in tests / first-run) ────
def create_all_tables() -> None:
    """
    Create database schema from ORM metadata.
    In production use Alembic migrations instead.
    """
    # Import all models so their metadata is registered with Base
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def drop_all_tables() -> None:
    """Tear down schema – used in test teardown ONLY."""
    import app.models  # noqa: F401
    Base.metadata.drop_all(bind=engine)

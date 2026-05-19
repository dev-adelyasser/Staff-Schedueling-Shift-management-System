"""
backend/tests/conftest.py
──────────────────────────
Shared pytest fixtures for Person 2's test suite.

Unit tests:   inject mock DB sessions — no real database.
Integration:  use a real PostgreSQL test DB with SAVEPOINT rollback so each
              test is atomic and independent.

Environment variables (required for integration tests):
  TEST_DATABASE_URL — PostgreSQL DSN for the test database.
  SECRET_KEY        — any string (tests supply their own tokens).
"""

import os

# Must be set before any `from app.*` import so pydantic-settings resolves.
os.environ.setdefault("SECRET_KEY", "test-secret-not-for-production")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL", "postgresql://sssms:sssms@localhost:5432/sssms_test"
    ),
)
os.environ.setdefault("APP_ENV", "testing")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db
from app.main import app
from app.models import (  # ensure all models are registered on Base.metadata
    AuditLog,
    AttendanceRecord,
    Shift,
    StaffAssignment,
    StaffAvailability,
    SwapRequest,
    User,
)
from app.models.user import Base


# ── Integration DB fixtures (real PostgreSQL + SAVEPOINT rollback) ────────── #

@pytest.fixture(scope="session")
def engine():
    url = os.environ["DATABASE_URL"]
    eng = create_engine(url, future=True)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(engine, tables):
    """
    Yields a transactional Session that is rolled back after each test.
    Uses a SAVEPOINT so tests can call commit() internally.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    # Nested SAVEPOINT — individual commits become SAVEPOINT RELEASE
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    """TestClient with the test DB session injected as the `get_db` override."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

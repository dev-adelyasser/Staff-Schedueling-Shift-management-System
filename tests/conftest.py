"""
tests/conftest.py
─────────────────
Pytest root configuration.

Testing Pyramid wiring
──────────────────────
  70 % Unit        → tests/unit/       (pure function; no DB; mock repos)
  20 % Integration → tests/integration/ (real SQLite in-memory DB; real repos)
  10 % E2E         → tests/e2e/        (full HTTP via TestClient or Playwright)

Key design decisions:
  • The integration DB session OVERRIDES FastAPI's get_db dependency so that
    every HTTP request in integration tests uses our controlled in-memory DB.
  • Unit tests NEVER touch the DB – they import and call functions/services
    directly, using mocks for the repository layer.
  • Each test that touches the DB runs inside a SAVEPOINT transaction that is
    rolled back after the test → perfect isolation with zero cost.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db

# ══════════════════════════════════════════════════════════════
#  Test Database  –  SQLite in-memory (fast, isolated)
# ══════════════════════════════════════════════════════════════

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite + pytest
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
)


# ══════════════════════════════════════════════════════════════
#  Session-scoped schema creation
# ══════════════════════════════════════════════════════════════

@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """
    Create all ORM tables once per test session.
    Dropped after session ends.
    """
    import app.models  # noqa: F401 – ensures metadata is populated
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


# ══════════════════════════════════════════════════════════════
#  Per-test transaction rollback  (Integration layer)
# ══════════════════════════════════════════════════════════════

@pytest.fixture()
def db_session() -> Session:
    """
    Provides a clean DB session for each test, wrapped in a
    SAVEPOINT that is rolled back when the test finishes.

    Result: zero pollution between tests, no teardown SQL needed.
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    session = TestingSessionLocal(bind=connection)

    # Wrap every ORM flush in a nested SAVEPOINT
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ══════════════════════════════════════════════════════════════
#  FastAPI dependency override
# ══════════════════════════════════════════════════════════════

@pytest.fixture()
def client(db_session: Session) -> TestClient:
    """
    HTTP test client with the DB overridden to use the
    test session – guarantees integration tests hit the same
    in-memory DB that the fixture controls.
    """
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # session lifecycle managed by db_session fixture

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════
#  Shared test data fixtures  (see tests/fixtures/ for factories)
# ══════════════════════════════════════════════════════════════

@pytest.fixture()
def admin_user_payload() -> dict:
    return {
        "email": "admin@example.com",
        "full_name": "Admin User",
        "password": "Admin@12345",
        "role": "admin",
    }


@pytest.fixture()
def staff_user_payload() -> dict:
    return {
        "email": "staff@example.com",
        "full_name": "Staff Member",
        "password": "Staff@12345",
        "role": "staff",
    }

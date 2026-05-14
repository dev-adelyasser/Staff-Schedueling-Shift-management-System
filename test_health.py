"""
tests/unit/test_health.py
──────────────────────────
Testing Pyramid layer  : Unit (target 70 %)
Isolation guarantee    : No database, no external services, no auth.
                         The ASGI app is driven entirely in-process via
                         FastAPI's synchronous TestClient.

Why sync TestClient, not AsyncClient
──────────────────────────────────────
The rest of this project's test suite uses FastAPI's synchronous
TestClient (see tests/conftest.py).  Mixing async and sync clients in
one session is possible but needlessly complex at this stage.
TestClient wraps the ASGI app in a sync interface — it is still exercising
the full async FastAPI stack; it just hides the event-loop machinery.

Failing-Test-First rationale
──────────────────────────────
This file targets endpoints that exist in app/main.py.  On a checkout
where main.py is absent or has import errors (missing database.py,
config.py, etc.), pytest collection will raise ImportError — that IS
the expected "red" state.  Fix the imports to move to "green".

Boundary contracts under test
──────────────────────────────
  GET /health
  ─────────────────────────────────────────────────────────
  status code        : 200
  body["status"]     : "ok"          ← matches main.py exactly
  body["environment"]: non-empty str
  body["version"]    : non-empty str
  body["service"]    : non-empty str

  GET /health/db
  ─────────────────────────────────────────────────────────
  status code        : 200 or 503    ← depends on DB reachability
  body["status"]     : "ok" | "degraded"
  body["database"]   : "connected" | "unreachable"

Note: tests/conftest.py sets SECRET_KEY, DATABASE_URL, APP_ENV before
any import so Settings() never raises ValidationError during collection.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def unit_client() -> TestClient:
    """
    Lightweight test client for the health unit tests.

    Deliberately does NOT use the `client` fixture from conftest.py —
    that fixture injects a DB session (integration-layer concern).
    Unit tests must stay DB-free; we instantiate TestClient directly.
    """
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── /health tests ─────────────────────────────────────────────────────────────

def test_health_returns_200(unit_client: TestClient) -> None:
    """
    Boundary assertion 1 of 5: HTTP status code must be exactly 200.

    Any other status (404 = route missing, 500 = startup error) means
    the CI pipeline must NOT proceed to integration tests.
    """
    response = unit_client.get("/health")
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        "Verify GET /health is defined in app/main.py."
    )


def test_health_status_is_ok(unit_client: TestClient) -> None:
    """
    Boundary assertion 2 of 5: body["status"] must equal "ok".

    Contract: app/main.py health() returns {"status": "ok", ...}.
    This string is the agreed handshake with Member 2's frontend ping.
    """
    body = unit_client.get("/health").json()

    assert "status" in body, "Response JSON is missing the 'status' key."
    assert body["status"] == "ok", (
        f"Expected status='ok' but got status='{body['status']}'."
    )


def test_health_contains_environment(unit_client: TestClient) -> None:
    """
    Boundary assertion 3 of 5: environment key must be present and non-empty.

    Member 2's frontend uses this to display an environment badge
    ("TESTING", "PRODUCTION") so a missing value is a contract violation.
    """
    body = unit_client.get("/health").json()

    assert "environment" in body, "Response JSON is missing the 'environment' key."
    assert isinstance(body["environment"], str) and body["environment"], (
        "The 'environment' field must be a non-empty string."
    )


def test_health_contains_version(unit_client: TestClient) -> None:
    """
    Boundary assertion 4 of 5: version key must be present and non-empty.

    CI tooling compares this against the release tag to catch stale images.
    """
    body = unit_client.get("/health").json()

    assert "version" in body, "Response JSON is missing the 'version' key."
    assert isinstance(body["version"], str) and body["version"], (
        "The 'version' field must be a non-empty string."
    )


def test_health_contains_service(unit_client: TestClient) -> None:
    """
    Boundary assertion 5 of 5: service key must be present and non-empty.

    app/main.py includes "service": settings.app_name; this test locks
    that field into the contract so future refactors can't silently drop it.
    """
    body = unit_client.get("/health").json()

    assert "service" in body, "Response JSON is missing the 'service' key."
    assert isinstance(body["service"], str) and body["service"], (
        "The 'service' field must be a non-empty string."
    )


# ── /health/db tests ──────────────────────────────────────────────────────────

def test_health_db_returns_valid_status(unit_client: TestClient) -> None:
    """
    DB readiness probe: status code must be 200 (DB reachable) or 503 (not).

    In the unit test environment SQLite is used so the DB IS reachable
    and we expect 200.  This test mocks check_connection() returning True
    so it never depends on a real Postgres connection.
    """
    with patch("app.main.check_connection", return_value=True):
        response = unit_client.get("/health/db")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_health_db_returns_503_when_db_unreachable(unit_client: TestClient) -> None:
    """
    DB readiness probe degraded path: when check_connection() returns
    False the endpoint must return HTTP 503 and status="degraded".

    This is a pure unit test — check_connection is mocked; no real DB
    is brought down.
    """
    with patch("app.main.check_connection", return_value=False):
        response = unit_client.get("/health/db")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unreachable"

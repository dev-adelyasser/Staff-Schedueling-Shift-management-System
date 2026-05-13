"""
tests/e2e/test_health_e2e.py
─────────────────────────────
E2E smoke test (10 % of pyramid).
Uses TestClient against the full app stack.
Playwright-based tests live in /e2e/ directory.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def e2e_client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint_returns_ok(e2e_client):
    resp = e2e_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body


def test_openapi_schema_accessible(e2e_client):
    resp = e2e_client.get("/openapi.json")
    assert resp.status_code == 200
    assert "paths" in resp.json()


def test_docs_accessible(e2e_client):
    resp = e2e_client.get("/docs")
    assert resp.status_code == 200


def test_unknown_route_returns_404(e2e_client):
    resp = e2e_client.get("/api/v1/nonexistent")
    assert resp.status_code == 404

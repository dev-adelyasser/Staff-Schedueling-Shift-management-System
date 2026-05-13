"""
tests/integration/test_users_api.py
────────────────────────────────────
Integration tests for the /api/v1/users endpoints.

Target: 20 % of the test suite (real HTTP + real DB, controlled session).
Uses the `client` fixture from conftest.py which overrides get_db.
"""

import pytest


BASE = "/api/v1/users"


class TestCreateUser:

    def test_create_user_returns_201(self, client, admin_user_payload):
        resp = client.post(BASE + "/", json=admin_user_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == admin_user_payload["email"]
        assert "hashed_password" not in data   # Information Hiding guard

    def test_duplicate_email_returns_409(self, client, admin_user_payload):
        client.post(BASE + "/", json=admin_user_payload)
        resp = client.post(BASE + "/", json=admin_user_payload)
        assert resp.status_code == 409

    def test_weak_password_returns_422(self, client):
        resp = client.post(BASE + "/", json={
            "email": "test@example.com",
            "full_name": "Test",
            "password": "weak",
            "role": "staff",
        })
        assert resp.status_code == 422


class TestGetUser:

    def test_get_existing_user(self, client, admin_user_payload):
        create_resp = client.post(BASE + "/", json=admin_user_payload)
        user_id = create_resp.json()["id"]
        resp = client.get(f"{BASE}/{user_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == user_id

    def test_get_nonexistent_returns_404(self, client):
        resp = client.get(f"{BASE}/99999")
        assert resp.status_code == 404


class TestListUsers:

    def test_list_returns_array(self, client, staff_user_payload):
        client.post(BASE + "/", json=staff_user_payload)
        resp = client.get(BASE + "/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

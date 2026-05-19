"""
backend/tests/integration/test_shifts_api.py
──────────────────────────────────────────────
Integration tests — 20% of test pyramid.

These tests hit the real FastAPI app (via TestClient) against a real
PostgreSQL database (SAVEPOINT-wrapped via conftest.py fixtures).

Markers: @pytest.mark.integration (skip when TEST_DATABASE_URL is not set).
"""

import io
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

pytestmark = pytest.mark.integration

_SECRET = os.environ.get("SECRET_KEY", "test-secret-not-for-production")


def _make_token(user_id: int, role: str, token_version: int = 1) -> str:
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, _SECRET, algorithm="HS256")


# ── Fixtures ────────────────────────────────────────────────────────────────── #

@pytest.fixture()
def admin_headers(db_session):
    from app.models.user import User, UserRole
    from app.core.security import hash_password

    user = User(
        email="admin_shift_test@test.com",
        first_name="Admin",
        last_name="Test",
        hashed_password=hash_password("Password1!"),
        role=UserRole.ADMIN,
        is_active=True,
        is_deleted=False,
        token_version=1,
    )
    db_session.add(user)
    db_session.flush()
    token = _make_token(user.id, "ADMIN")
    return {"Authorization": f"Bearer {token}"}, user


@pytest.fixture()
def staff_headers(db_session):
    from app.models.user import User, UserRole
    from app.core.security import hash_password

    user = User(
        email="staff_shift_test@test.com",
        first_name="Staff",
        last_name="Test",
        hashed_password=hash_password("Password1!"),
        role=UserRole.STAFF,
        is_active=True,
        is_deleted=False,
        token_version=1,
    )
    db_session.add(user)
    db_session.flush()
    token = _make_token(user.id, "STAFF")
    return {"Authorization": f"Bearer {token}"}, user


# ── POST /api/v1/shifts — happy path ────────────────────────────────────────── #

def test_create_shift_returns_201(client, admin_headers):
    headers, _ = admin_headers
    payload = {
        "title": "Morning Shift",
        "start_time": "2026-07-01T08:00:00+00:00",
        "end_time": "2026-07-01T16:00:00+00:00",
        "department_id": 1,
        "headcount": 2,
    }
    resp = client.post("/api/v1/shifts/", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Morning Shift"
    assert "id" in data
    # ShiftResponseSchema must NOT expose created_by, updated_at, is_deleted
    assert "created_by" not in data
    assert "is_deleted" not in data
    assert "updated_at" not in data


def test_create_shift_requires_admin(client, staff_headers):
    headers, _ = staff_headers
    payload = {
        "title": "Shift",
        "start_time": "2026-07-02T08:00:00+00:00",
        "end_time": "2026-07-02T16:00:00+00:00",
        "department_id": 1,
    }
    resp = client.post("/api/v1/shifts/", json=payload, headers=headers)
    assert resp.status_code == 403


def test_create_shift_rejects_end_before_start_422(client, admin_headers):
    headers, _ = admin_headers
    payload = {
        "title": "Bad Shift",
        "start_time": "2026-07-01T16:00:00+00:00",
        "end_time": "2026-07-01T08:00:00+00:00",  # end < start
        "department_id": 1,
    }
    resp = client.post("/api/v1/shifts/", json=payload, headers=headers)
    assert resp.status_code == 422


# ── GET /api/v1/shifts ───────────────────────────────────────────────────────── #

def test_list_shifts_accessible_to_staff(client, staff_headers):
    headers, _ = staff_headers
    resp = client.get("/api/v1/shifts/", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_list_shifts_pagination(client, admin_headers):
    headers, _ = admin_headers
    # Create 3 shifts first
    base = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    for i in range(3):
        client.post("/api/v1/shifts/", json={
            "title": f"Shift {i}",
            "start_time": (base + timedelta(days=i, hours=0)).isoformat(),
            "end_time": (base + timedelta(days=i, hours=8)).isoformat(),
            "department_id": 1,
        }, headers=headers)

    resp = client.get("/api/v1/shifts/?skip=0&limit=2", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 2


# ── POST /api/v1/shifts/{id}/assign ──────────────────────────────────────────── #

def test_assign_staff_to_shift(client, admin_headers, db_session):
    headers, admin = admin_headers
    # Create staff user
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    staff = User(
        email="assignee@test.com", first_name="A", last_name="B",
        hashed_password=hash_password("pw"), role=UserRole.STAFF,
        is_active=True, is_deleted=False, token_version=1,
    )
    db_session.add(staff)
    db_session.flush()

    # Create shift
    resp = client.post("/api/v1/shifts/", json={
        "title": "Assign Test",
        "start_time": "2026-09-01T08:00:00+00:00",
        "end_time": "2026-09-01T16:00:00+00:00",
        "department_id": 3,
    }, headers=headers)
    assert resp.status_code == 201
    shift_id = resp.json()["id"]

    # Assign staff
    resp2 = client.post(
        f"/api/v1/shifts/{shift_id}/assign",
        json={"staff_id": staff.id},
        headers=headers,
    )
    assert resp2.status_code == 200


def test_assign_staff_conflict_returns_409(client, admin_headers, db_session):
    headers, _ = admin_headers
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    staff = User(
        email="staff_conflict@test.com", first_name="C", last_name="D",
        hashed_password=hash_password("pw"), role=UserRole.STAFF,
        is_active=True, is_deleted=False, token_version=1,
    )
    db_session.add(staff)
    db_session.flush()

    # Two overlapping shifts
    for title, hour in [("S1", 8), ("S2", 10)]:
        resp = client.post("/api/v1/shifts/", json={
            "title": title,
            "start_time": f"2026-10-01T{hour:02d}:00:00+00:00",
            "end_time": f"2026-10-01T{hour + 8:02d}:00:00+00:00",
            "department_id": 4,
        }, headers=headers)
        assert resp.status_code == 201

    shifts = client.get("/api/v1/shifts/?department_id=4", headers=headers).json()["items"]
    assert len(shifts) >= 2

    s1_id, s2_id = shifts[0]["id"], shifts[1]["id"]
    r1 = client.post(f"/api/v1/shifts/{s1_id}/assign", json={"staff_id": staff.id}, headers=headers)
    assert r1.status_code == 200

    # Second assign overlaps first → 409
    r2 = client.post(f"/api/v1/shifts/{s2_id}/assign", json={"staff_id": staff.id}, headers=headers)
    assert r2.status_code == 409


# ── POST /api/v1/shifts/bulk-upload ──────────────────────────────────────────── #

def test_bulk_upload_all_valid_returns_201(client, admin_headers):
    headers, _ = admin_headers
    csv_data = (
        "title,start_time,end_time,department_id,headcount\n"
        "BulkA,2026-11-01T08:00:00+00:00,2026-11-01T16:00:00+00:00,5,1\n"
        "BulkB,2026-11-02T08:00:00+00:00,2026-11-02T16:00:00+00:00,5,2\n"
    )
    resp = client.post(
        "/api/v1/shifts/bulk-upload",
        files={"file": ("shifts.csv", io.BytesIO(csv_data.encode()), "text/csv")},
        headers=headers,
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert len(data["created"]) == 2
    assert data["errors"] == []


def test_bulk_upload_wrong_extension_400(client, admin_headers):
    headers, _ = admin_headers
    resp = client.post(
        "/api/v1/shifts/bulk-upload",
        files={"file": ("shifts.txt", b"not csv", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 400


# ── Audit trail ──────────────────────────────────────────────────────────────── #

def test_audit_log_written_on_create(client, admin_headers, db_session):
    from app.models.audit_log import AuditLog
    from sqlalchemy import select

    headers, _ = admin_headers
    client.post("/api/v1/shifts/", json={
        "title": "AuditShift",
        "start_time": "2026-12-01T08:00:00+00:00",
        "end_time": "2026-12-01T16:00:00+00:00",
        "department_id": 9,
    }, headers=headers)

    logs = list(db_session.scalars(
        select(AuditLog).where(AuditLog.target_table == "shifts")
    ))
    assert any(log.action_type.value == "CREATE" for log in logs)

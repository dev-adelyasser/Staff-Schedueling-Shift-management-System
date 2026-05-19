"""
backend/tests/integration/test_swaps_api.py
──────────────────────────────────────────────
Integration tests for the Shift Swap workflow (AU-08, HR-01, HR-03).
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

pytestmark = pytest.mark.integration

_SECRET = os.environ.get("SECRET_KEY", "test-secret-not-for-production")


def _token(user_id: int, role: str) -> str:
    return jwt.encode(
        {
            "sub": str(user_id),
            "ver": 1,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        _SECRET,
        algorithm="HS256",
    )


# ── Fixtures ────────────────────────────────────────────────────────────────── #

@pytest.fixture()
def staff_user(db_session):
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    u = User(
        email="swapstaff@test.com", first_name="Swap", last_name="Staff",
        hashed_password=hash_password("pw"), role=UserRole.STAFF,
        is_active=True, is_deleted=False, token_version=1,
    )
    db_session.add(u)
    db_session.flush()
    return u, {"Authorization": f"Bearer {_token(u.id, 'STAFF')}"}


@pytest.fixture()
def admin_user(db_session):
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    u = User(
        email="swapadmin@test.com", first_name="Swap", last_name="Admin",
        hashed_password=hash_password("pw"), role=UserRole.ADMIN,
        is_active=True, is_deleted=False, token_version=1,
    )
    db_session.add(u)
    db_session.flush()
    return u, {"Authorization": f"Bearer {_token(u.id, 'ADMIN')}"}


@pytest.fixture()
def two_shifts(client, admin_user, db_session):
    _, headers = admin_user
    base = datetime(2027, 1, 1, 8, 0, tzinfo=timezone.utc)
    ids = []
    for i in range(2):
        r = client.post("/api/v1/shifts/", json={
            "title": f"SwapShift{i}",
            "start_time": (base + timedelta(days=i * 2)).isoformat(),
            "end_time": (base + timedelta(days=i * 2, hours=8)).isoformat(),
            "department_id": 10,
        }, headers=headers)
        assert r.status_code == 201
        ids.append(r.json()["id"])
    return ids[0], ids[1]


# ── POST /api/v1/swaps ───────────────────────────────────────────────────────── #

def test_create_swap_returns_201_pending(client, staff_user, two_shifts):
    _, headers = staff_user
    s1, s2 = two_shifts
    resp = client.post("/api/v1/swaps/", json={
        "requester_shift_id": s1,
        "target_shift_id": s2,
        "reason": "Personal conflict",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "PENDING"


def test_create_swap_admin_forbidden(client, admin_user, two_shifts):
    _, headers = admin_user
    s1, s2 = two_shifts
    resp = client.post("/api/v1/swaps/", json={
        "requester_shift_id": s1,
        "target_shift_id": s2,
    }, headers=headers)
    # Admin does not have STAFF role — should be 403
    assert resp.status_code == 403


def test_create_swap_same_shift_ids_422(client, staff_user):
    _, headers = staff_user
    same = str(uuid.uuid4())
    resp = client.post("/api/v1/swaps/", json={
        "requester_shift_id": same,
        "target_shift_id": same,
    }, headers=headers)
    assert resp.status_code == 422


# ── Approve / Reject ─────────────────────────────────────────────────────────── #

def test_approve_swap_returns_approved(client, staff_user, admin_user, two_shifts):
    _, staff_headers = staff_user
    _, admin_headers = admin_user
    s1, s2 = two_shifts

    r = client.post("/api/v1/swaps/", json={
        "requester_shift_id": s1, "target_shift_id": s2,
    }, headers=staff_headers)
    swap_id = r.json()["id"]

    resp = client.post(f"/api/v1/swaps/{swap_id}/approve", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"


def test_reject_swap_returns_rejected(client, staff_user, admin_user, two_shifts):
    _, staff_headers = staff_user
    _, admin_headers = admin_user
    s1, s2 = two_shifts

    r = client.post("/api/v1/swaps/", json={
        "requester_shift_id": s1, "target_shift_id": s2,
    }, headers=staff_headers)
    swap_id = r.json()["id"]

    resp = client.post(f"/api/v1/swaps/{swap_id}/reject", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"


def test_approve_already_approved_returns_409(client, staff_user, admin_user, two_shifts):
    """AU-08: double-approve must produce HTTP 409."""
    _, staff_headers = staff_user
    _, admin_headers = admin_user
    s1, s2 = two_shifts

    r = client.post("/api/v1/swaps/", json={
        "requester_shift_id": s1, "target_shift_id": s2,
    }, headers=staff_headers)
    swap_id = r.json()["id"]

    client.post(f"/api/v1/swaps/{swap_id}/approve", headers=admin_headers)
    resp2 = client.post(f"/api/v1/swaps/{swap_id}/approve", headers=admin_headers)
    assert resp2.status_code == 409


# ── HR-03 rate limit ────────────────────────────────────────────────────────── #

def test_swap_rate_limit_429(client, db_session, admin_user):
    """
    Inject 10 swap_request rows within the last hour for a user,
    then verify the 11th request returns 429 with Retry-After header.
    """
    from app.models.swap_request import SwapRequest, SwapStatus
    from datetime import timezone

    _, admin_headers = admin_user

    # Create staff user
    from app.models.user import User, UserRole
    from app.core.security import hash_password
    staff = User(
        email="ratelimit_staff@test.com", first_name="R", last_name="L",
        hashed_password=hash_password("pw"), role=UserRole.STAFF,
        is_active=True, is_deleted=False, token_version=1,
    )
    db_session.add(staff)
    db_session.flush()
    staff_headers = {"Authorization": f"Bearer {_token(staff.id, 'STAFF')}"}

    # Directly insert 10 rows to exhaust the rate limit
    now = datetime.now(timezone.utc)
    for _ in range(10):
        sr = SwapRequest(
            requester_id=staff.id,
            requester_shift_id=uuid.uuid4(),
            target_shift_id=uuid.uuid4(),
            status=SwapStatus.PENDING,
            created_at=now,
        )
        db_session.add(sr)
    db_session.flush()

    resp = client.post("/api/v1/swaps/", json={
        "requester_shift_id": str(uuid.uuid4()),
        "target_shift_id": str(uuid.uuid4()),
    }, headers=staff_headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers

"""
backend/tests/unit/test_swap_service.py
──────────────────────────────────────────
Unit tests for SwapService — state machine, rate limiting, SELECT FOR UPDATE.
"""

import os
os.environ.setdefault("SECRET_KEY", "unit-test-secret-not-for-production")
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("APP_ENV", "testing")

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models.swap_request import SwapStatus
from app.schemas.swap import SwapRequestCreateSchema
from app.services.swap_service import (
    SwapConflictError,
    SwapNotFoundError,
    SwapRateLimitError,
    SwapService,
)


def _make_swap(status: SwapStatus = SwapStatus.PENDING):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.requester_id = 1
    m.requester_shift_id = uuid.uuid4()
    m.target_shift_id = uuid.uuid4()
    m.reason = "swap me please"
    m.status = status
    m.created_at = datetime.now(timezone.utc)
    m.resolved_at = None
    m.resolved_by = None
    return m


def _make_service(*, recent_count: int = 0, swap=None):
    db = MagicMock()
    svc = SwapService(db)
    svc._repo = MagicMock()
    svc._audit = MagicMock()
    svc._repo.count_recent_by_user.return_value = recent_count
    svc._repo.create.return_value = swap or _make_swap()
    svc._repo.get_for_update.return_value = swap or _make_swap()
    svc._repo.set_status.side_effect = lambda sw, st, resolved_by: (
        setattr(sw, "status", st) or sw
    )
    return svc


# ── Create ──────────────────────────────────────────────────────────────────── #

def test_create_swap_happy_path():
    svc = _make_service(recent_count=0)
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    payload = SwapRequestCreateSchema(
        requester_shift_id=s1, target_shift_id=s2
    )
    result = svc.create_swap(payload, requester_id=1)
    svc._repo.create.assert_called_once()
    svc._audit.record.assert_called_once()


def test_create_swap_rate_limit_exceeded():
    """HR-03: 10th+ request in 1 hour raises SwapRateLimitError."""
    svc = _make_service(recent_count=10)
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    payload = SwapRequestCreateSchema(requester_shift_id=s1, target_shift_id=s2)
    with pytest.raises(SwapRateLimitError):
        svc.create_swap(payload, requester_id=1)


def test_create_swap_at_limit_boundary_passes():
    """9th request is still within the limit."""
    svc = _make_service(recent_count=9)
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    payload = SwapRequestCreateSchema(requester_shift_id=s1, target_shift_id=s2)
    svc.create_swap(payload, requester_id=1)  # must not raise


# ── Schema validation ────────────────────────────────────────────────────────── #

def test_schema_rejects_same_shift_ids():
    same = uuid.uuid4()
    with pytest.raises(Exception, match="different"):
        SwapRequestCreateSchema(requester_shift_id=same, target_shift_id=same)


def test_schema_rejects_reason_over_500_chars():
    with pytest.raises(Exception):
        SwapRequestCreateSchema(
            requester_shift_id=uuid.uuid4(),
            target_shift_id=uuid.uuid4(),
            reason="x" * 501,
        )


# ── Approve ──────────────────────────────────────────────────────────────────── #

def test_approve_pending_swap_succeeds():
    swap = _make_swap(SwapStatus.PENDING)
    svc = _make_service(swap=swap)
    svc.approve_swap(swap.id, actor_id=99)
    svc._repo.set_status.assert_called_once()
    svc._audit.record.assert_called_once()


def test_approve_already_approved_raises_conflict():
    """AU-08: PENDING → APPROVED only; re-approving raises SwapConflictError."""
    swap = _make_swap(SwapStatus.APPROVED)
    svc = _make_service(swap=swap)
    with pytest.raises(SwapConflictError):
        svc.approve_swap(swap.id, actor_id=99)


def test_approve_rejected_swap_raises_conflict():
    swap = _make_swap(SwapStatus.REJECTED)
    svc = _make_service(swap=swap)
    with pytest.raises(SwapConflictError):
        svc.approve_swap(swap.id, actor_id=99)


def test_approve_missing_swap_raises_not_found():
    svc = _make_service()
    svc._repo.get_for_update.return_value = None
    with pytest.raises(SwapNotFoundError):
        svc.approve_swap(uuid.uuid4(), actor_id=99)


# ── Reject ───────────────────────────────────────────────────────────────────── #

def test_reject_pending_swap_succeeds():
    swap = _make_swap(SwapStatus.PENDING)
    svc = _make_service(swap=swap)
    svc.reject_swap(swap.id, actor_id=99)
    svc._repo.set_status.assert_called_once()
    svc._audit.record.assert_called_once()


def test_reject_already_rejected_raises_conflict():
    swap = _make_swap(SwapStatus.REJECTED)
    svc = _make_service(swap=swap)
    with pytest.raises(SwapConflictError):
        svc.reject_swap(swap.id, actor_id=99)


def test_reject_missing_swap_raises_not_found():
    svc = _make_service()
    svc._repo.get_for_update.return_value = None
    with pytest.raises(SwapNotFoundError):
        svc.reject_swap(uuid.uuid4(), actor_id=99)


# ── HR-02: audit written for every state transition ─────────────────────────── #

def test_audit_written_on_approve():
    swap = _make_swap(SwapStatus.PENDING)
    svc = _make_service(swap=swap)
    svc.approve_swap(swap.id, actor_id=5)
    # Exactly one audit record for this transition
    assert svc._audit.record.call_count == 1


def test_audit_written_on_reject():
    swap = _make_swap(SwapStatus.PENDING)
    svc = _make_service(swap=swap)
    svc.reject_swap(swap.id, actor_id=5)
    assert svc._audit.record.call_count == 1

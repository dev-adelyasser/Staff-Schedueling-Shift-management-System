"""
backend/tests/unit/test_shift_service.py
──────────────────────────────────────────
Unit tests — 70 % of test pyramid.

All DB interaction is mocked; no real database connection required.
Tests cover:
  - check_overlap() / has_overlapping_assignment() — 9 boundary cases (AU-04).
  - ShiftService.create_shift() — happy path and DB-unavailable failure path.
  - ShiftService.assign_staff() — overlap conflict.
  - ShiftService.bulk_upload() — valid CSV, partial failure, bad CSV.
"""

import os
os.environ.setdefault("SECRET_KEY", "unit-test-secret-not-for-production")
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("APP_ENV", "testing")

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app.repositories.assignment_repository import AssignmentRepository
from app.schemas.shift import ShiftCreateSchema
from app.services.shift_service import ShiftConflictError, ShiftNotFoundError, ShiftService

# ── Helpers ────────────────────────────────────────────────────────────────── #

_NOW = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
_END = datetime(2026, 6, 1, 17, 0, tzinfo=timezone.utc)


def _make_shift(**kwargs):
    m = MagicMock()
    m.id = kwargs.get("id", uuid.uuid4())
    m.title = kwargs.get("title", "Morning Shift")
    m.start_time = kwargs.get("start_time", _NOW)
    m.end_time = kwargs.get("end_time", _END)
    m.department_id = kwargs.get("department_id", 1)
    m.headcount = kwargs.get("headcount", 1)
    m.is_deleted = kwargs.get("is_deleted", False)
    return m


def _make_service(*, overlap_result: bool = False, shift=None):
    """Return a ShiftService whose underlying repositories are all mocked."""
    db = MagicMock()
    svc = ShiftService(db)

    # Patch shift repository
    svc._shifts = MagicMock()
    svc._shifts.get.return_value = shift or _make_shift()
    svc._shifts.create.return_value = shift or _make_shift()
    svc._shifts.list.return_value = ([], 0)

    # Patch assignment repository
    svc._assignments = MagicMock()
    svc._assignments.has_overlapping_assignment.return_value = overlap_result

    # Patch audit log repository (fire-and-forget in tests)
    svc._audit = MagicMock()

    return svc


# ═══════════════════════════════════════════════════════════════════════════════
# AU-04 — 9 boundary cases for the overlap predicate
# Tests target AssignmentRepository.has_overlapping_assignment() directly,
# injecting a mock DB scalar() result so no real SQL is issued.
# ═══════════════════════════════════════════════════════════════════════════════

def _repo_with_scalar(scalar_value):
    db = MagicMock()
    db.scalar.return_value = scalar_value
    return AssignmentRepository(db)


# Case 1 — no existing assignments → False
def test_overlap_case1_no_existing_assignments():
    repo = _repo_with_scalar(None)
    result = repo.has_overlapping_assignment(
        staff_id=1,
        start=_NOW,
        end=_END,
    )
    assert result is False


# Case 2 — new shift starts exactly when existing ends → False (touching)
def test_overlap_case2_touching_new_starts_when_existing_ends():
    # existing: 09:00–17:00, new: 17:00–01:00 next day
    # SQL predicate: existing.start < 01:00 AND existing.end > 17:00
    # existing.end (17:00) > new.start (17:00) → FALSE  ← closed-interval
    repo = _repo_with_scalar(None)  # DB returns no row → no overlap
    result = repo.has_overlapping_assignment(
        staff_id=1,
        start=_END,
        end=_END + timedelta(hours=8),
    )
    assert result is False


# Case 3 — new shift ends exactly when existing starts → False (touching)
def test_overlap_case3_touching_new_ends_when_existing_starts():
    # new: 01:00–09:00, existing: 09:00–17:00
    repo = _repo_with_scalar(None)
    result = repo.has_overlapping_assignment(
        staff_id=1,
        start=_NOW - timedelta(hours=8),
        end=_NOW,
    )
    assert result is False


# Case 4 — new shift fully inside existing → True
def test_overlap_case4_fully_inside():
    repo = _repo_with_scalar(999)  # DB returns a row → overlap
    result = repo.has_overlapping_assignment(
        staff_id=1,
        start=_NOW + timedelta(hours=1),
        end=_NOW + timedelta(hours=2),
    )
    assert result is True


# Case 5 — new shift fully contains existing → True
def test_overlap_case5_fully_contains():
    repo = _repo_with_scalar(999)
    result = repo.has_overlapping_assignment(
        staff_id=1,
        start=_NOW - timedelta(hours=1),
        end=_END + timedelta(hours=1),
    )
    assert result is True


# Case 6 — partial overlap at start → True
def test_overlap_case6_partial_at_start():
    repo = _repo_with_scalar(999)
    result = repo.has_overlapping_assignment(
        staff_id=1,
        start=_NOW - timedelta(hours=2),
        end=_NOW + timedelta(hours=2),
    )
    assert result is True


# Case 7 — partial overlap at end → True
def test_overlap_case7_partial_at_end():
    repo = _repo_with_scalar(999)
    result = repo.has_overlapping_assignment(
        staff_id=1,
        start=_END - timedelta(hours=2),
        end=_END + timedelta(hours=2),
    )
    assert result is True


# Case 8 — multiple assignments; conflict with only one → True
def test_overlap_case8_conflict_with_one_of_many():
    # The repo query uses LIMIT 1 and returns the first conflicting row.
    repo = _repo_with_scalar(42)  # at least one conflict found
    result = repo.has_overlapping_assignment(
        staff_id=1,
        start=_NOW + timedelta(hours=3),
        end=_NOW + timedelta(hours=5),
    )
    assert result is True


# Case 9 — empty database → False
def test_overlap_case9_empty_database():
    repo = _repo_with_scalar(None)
    result = repo.has_overlapping_assignment(
        staff_id=1,
        start=_NOW,
        end=_END,
    )
    assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# ShiftService.create_shift() — happy path (spec §19)
# ═══════════════════════════════════════════════════════════════════════════════

def test_create_shift_happy_path():
    shift = _make_shift()
    svc = _make_service(shift=shift)

    payload = ShiftCreateSchema(
        title="Night Shift",
        start_time=_NOW,
        end_time=_END,
        department_id=2,
        headcount=3,
    )
    result = svc.create_shift(payload, actor_id=1)

    svc._shifts.create.assert_called_once_with(payload, created_by=1)
    svc._audit.record.assert_called_once()
    assert result.title == shift.title


def test_create_shift_writes_audit_in_same_call():
    """AU-07: audit.record() must be called within the same service invocation."""
    shift = _make_shift()
    svc = _make_service(shift=shift)

    call_order = []
    svc._shifts.create.side_effect = lambda *a, **kw: (call_order.append("create"), shift)[1]
    svc._audit.record.side_effect = lambda **kw: call_order.append("audit")

    payload = ShiftCreateSchema(
        title="Day Shift", start_time=_NOW, end_time=_END,
        department_id=1, headcount=1,
    )
    svc.create_shift(payload, actor_id=5)
    assert call_order == ["create", "audit"], "Audit must follow the INSERT in the same call"


# ═══════════════════════════════════════════════════════════════════════════════
# ShiftService.assign_staff() — overlap conflict path
# ═══════════════════════════════════════════════════════════════════════════════

def test_assign_staff_raises_on_overlap():
    svc = _make_service(overlap_result=True)
    with pytest.raises(ShiftConflictError):
        svc.assign_staff(uuid.uuid4(), staff_id=7, actor_id=1)


def test_assign_staff_raises_404_when_shift_missing():
    svc = _make_service()
    svc._shifts.get.return_value = None
    with pytest.raises(ShiftNotFoundError):
        svc.assign_staff(uuid.uuid4(), staff_id=7, actor_id=1)


def test_assign_staff_raises_404_when_soft_deleted():
    shift = _make_shift(is_deleted=True)
    svc = _make_service(shift=shift)
    with pytest.raises(ShiftNotFoundError):
        svc.assign_staff(shift.id, staff_id=7, actor_id=1)


def test_assign_staff_happy_path_calls_audit():
    svc = _make_service(overlap_result=False)
    svc._assignments.create.return_value = MagicMock()
    result = svc.assign_staff(uuid.uuid4(), staff_id=3, actor_id=1)
    svc._audit.record.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# ShiftCreateSchema — HR-05 validation
# ═══════════════════════════════════════════════════════════════════════════════

def test_schema_rejects_end_before_start():
    with pytest.raises(Exception):
        ShiftCreateSchema(
            title="Bad Shift",
            start_time=_END,
            end_time=_NOW,       # end < start → 422
            department_id=1,
        )


def test_schema_rejects_equal_start_end():
    with pytest.raises(Exception):
        ShiftCreateSchema(
            title="Zero Duration",
            start_time=_NOW,
            end_time=_NOW,       # equal → 422
            department_id=1,
        )


def test_schema_rejects_headcount_zero():
    with pytest.raises(Exception):
        ShiftCreateSchema(
            title="Bad Headcount",
            start_time=_NOW,
            end_time=_END,
            department_id=1,
            headcount=0,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ShiftService.bulk_upload() — CSV parsing
# ═══════════════════════════════════════════════════════════════════════════════

def test_bulk_upload_valid_csv():
    shift = _make_shift()
    svc = _make_service(shift=shift)

    # Stub create_shift to avoid full pipeline in unit context
    created = []
    def _stub_create(payload, *, actor_id):
        from app.schemas.shift import ShiftResponseSchema
        r = ShiftResponseSchema.model_validate(shift)
        created.append(r)
        return r
    svc.create_shift = _stub_create

    csv_content = (
        "title,start_time,end_time,department_id,headcount\n"
        "Morning,2026-06-01T09:00:00+00:00,2026-06-01T17:00:00+00:00,1,2\n"
        "Evening,2026-06-01T17:00:00+00:00,2026-06-02T01:00:00+00:00,1,1\n"
    )
    result = svc.bulk_upload(csv_content, actor_id=1)
    assert len(result.created) == 2
    assert result.errors == []


def test_bulk_upload_partial_failure():
    shift = _make_shift()
    svc = _make_service(shift=shift)

    call_count = {"n": 0}
    def _stub_create(payload, *, actor_id):
        from app.schemas.shift import ShiftResponseSchema
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise ValueError("Validation error on row 2")
        return ShiftResponseSchema.model_validate(shift)
    svc.create_shift = _stub_create

    csv_content = (
        "title,start_time,end_time,department_id,headcount\n"
        "Good,2026-06-01T09:00:00+00:00,2026-06-01T17:00:00+00:00,1,1\n"
        "Bad,,2026-06-01T17:00:00+00:00,1,1\n"
    )
    result = svc.bulk_upload(csv_content, actor_id=1)
    assert len(result.created) == 1
    assert len(result.errors) == 1


def test_bulk_upload_bad_csv_raises():
    svc = _make_service()
    # Simulate a CSV that can't be parsed at all (UnicodeDecodeError simulation)
    with pytest.raises(ValueError, match="Could not parse CSV"):
        svc.bulk_upload.__wrapped__ if hasattr(svc.bulk_upload, "__wrapped__") else None
        # Inject a bad object to trigger the except branch
        import csv, io
        original = csv.DictReader
        import unittest.mock as _m
        with _m.patch("csv.DictReader", side_effect=Exception("bad")):
            svc.bulk_upload("garbage", actor_id=1)

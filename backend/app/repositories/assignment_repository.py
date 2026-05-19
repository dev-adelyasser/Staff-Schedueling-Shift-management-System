"""
app/repositories/assignment_repository.py
──────────────────────────────────────────
DB queries for staff_assignments.

has_overlapping_assignment() is the AU-04 single-query overlap predicate.
It joins shifts to check start/end times, filtered on the indexed staff_id.
"""

import uuid
from datetime import datetime

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session

from app.models.shift import Shift
from app.models.staff_assignment import StaffAssignment


class AssignmentRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── AU-04 overlap check ────────────────────────────────────────────── #

    def has_overlapping_assignment(
        self,
        staff_id: int,
        start: datetime,
        end: datetime,
        *,
        exclude_shift_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Closed-interval overlap predicate (AU-04):
            existing.start_time < new.end_time
            AND existing.end_time > new.start_time

        Single ORM query, filtered on staff_id index — no Python-side filtering.
        """
        conditions = [
            StaffAssignment.staff_id == staff_id,
            Shift.is_deleted == False,  # noqa: E712
            Shift.start_time < end,
            Shift.end_time > start,
        ]
        if exclude_shift_id is not None:
            conditions.append(StaffAssignment.shift_id != exclude_shift_id)

        stmt = (
            select(StaffAssignment.id)
            .join(Shift, Shift.id == StaffAssignment.shift_id)
            .where(and_(*conditions))
            .limit(1)
        )
        return self._db.scalar(stmt) is not None

    # ── Writes ─────────────────────────────────────────────────────────── #

    def create(
        self,
        shift_id: uuid.UUID,
        staff_id: int,
        *,
        assigned_by: int,
    ) -> StaffAssignment:
        assignment = StaffAssignment(
            shift_id=shift_id,
            staff_id=staff_id,
            assigned_by=assigned_by,
        )
        self._db.add(assignment)
        self._db.flush()
        return assignment

    # ── Reads ──────────────────────────────────────────────────────────── #

    def list_for_shift(self, shift_id: uuid.UUID) -> list[StaffAssignment]:
        stmt = select(StaffAssignment).where(StaffAssignment.shift_id == shift_id)
        return list(self._db.scalars(stmt))

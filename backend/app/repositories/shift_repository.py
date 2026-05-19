"""
app/repositories/shift_repository.py
─────────────────────────────────────
DB queries for the Shift table only.  No domain rules, no HTTPException.
All reads use SQLAlchemy 2.0 style (select / scalars / scalar).
"""

import uuid
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.shift import Shift
from app.schemas.shift import ShiftCreateSchema


class ShiftRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Reads ──────────────────────────────────────────────────────────── #

    def get(self, shift_id: uuid.UUID) -> Shift | None:
        return self._db.get(Shift, shift_id)

    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        department_id: int | None = None,
    ) -> tuple[list[Shift], int]:
        base = select(Shift).where(Shift.is_deleted == False)  # noqa: E712
        if department_id is not None:
            base = base.where(Shift.department_id == department_id)
        total_stmt = select(func.count()).select_from(base.subquery())
        total: int = self._db.scalar(total_stmt) or 0
        rows = list(self._db.scalars(base.offset(skip).limit(limit)))
        return rows, total

    # ── Writes ─────────────────────────────────────────────────────────── #

    def create(self, payload: ShiftCreateSchema, *, created_by: int) -> Shift:
        shift = Shift(
            title=payload.title,
            start_time=payload.start_time,
            end_time=payload.end_time,
            department_id=payload.department_id,
            headcount=payload.headcount,
            created_by=created_by,
            is_deleted=False,
        )
        self._db.add(shift)
        self._db.flush()
        return shift

    def soft_delete(self, shift: Shift) -> None:
        shift.is_deleted = True
        self._db.flush()

"""
app/repositories/shift_repository.py
──────────────────────────────────────
Data-access layer for the Shift entity.
"""

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.models.shift import Shift
from app.core.validators import ShiftStatus


class ShiftRepository:

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, shift_id: int) -> Shift | None:
        return self._db.get(Shift, shift_id)

    def list_all(self, *, skip: int = 0, limit: int = 100) -> list[Shift]:
        stmt = select(Shift).offset(skip).limit(limit).order_by(Shift.start_time)
        return list(self._db.scalars(stmt).all())

    def list_by_user(self, user_id: int) -> list[Shift]:
        stmt = (
            select(Shift)
            .where(Shift.user_id == user_id)
            .order_by(Shift.start_time)
        )
        return list(self._db.scalars(stmt).all())

    def list_by_user_in_window(
        self, user_id: int, start: datetime, end: datetime
    ) -> list[Shift]:
        """Fetch shifts overlapping a time window – used for Padlock SHIFT-03."""
        stmt = (
            select(Shift)
            .where(
                and_(
                    Shift.user_id == user_id,
                    Shift.start_time >= start,
                    Shift.end_time   <= end,
                )
            )
            .order_by(Shift.start_time)
        )
        return list(self._db.scalars(stmt).all())

    def get_last_shift_for_user(self, user_id: int) -> Shift | None:
        """Returns the most recently ended shift for rest-period validation."""
        stmt = (
            select(Shift)
            .where(Shift.user_id == user_id)
            .order_by(Shift.end_time.desc())
            .limit(1)
        )
        return self._db.scalars(stmt).first()

    def create(self, **kwargs) -> Shift:
        shift = Shift(**kwargs)
        self._db.add(shift)
        self._db.flush()
        return shift

    def update(self, shift: Shift, **kwargs) -> Shift:
        for key, val in kwargs.items():
            if val is not None and hasattr(shift, key):
                setattr(shift, key, val)
        self._db.flush()
        return shift

    def delete(self, shift: Shift) -> None:
        self._db.delete(shift)
        self._db.flush()

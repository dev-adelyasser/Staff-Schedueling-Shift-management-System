from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.shift import Shift
from app.schemas.shift import ShiftCreate, ShiftUpdate


class ShiftRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list(self, *, skip: int = 0, limit: int = 100) -> list[Shift]:
        stmt = (
            select(Shift)
            .where(Shift.is_deleted == False)  # noqa: E712
            .offset(skip)
            .limit(limit)
        )
        return list(self._db.scalars(stmt))

    def get(self, shift_id: int) -> Shift | None:
        return self._db.get(Shift, shift_id)

    def create(self, payload: ShiftCreate, *, created_by: int) -> Shift:
        now = datetime.now(timezone.utc)
        shift = Shift(
            title=payload.title,
            start_time=payload.start_time,
            end_time=payload.end_time,
            department_id=payload.department_id,
            headcount=payload.headcount,
            created_by=created_by,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )
        self._db.add(shift)
        self._db.flush()
        return shift

    def update(self, shift: Shift, payload: ShiftUpdate) -> Shift:
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(shift, field, value)
        shift.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return shift

    def soft_delete(self, shift: Shift) -> None:
        """Spec security checklist: soft delete only — sets is_deleted flag."""
        now = datetime.now(timezone.utc)
        shift.is_deleted = True
        shift.deleted_at = now
        shift.updated_at = now
        self._db.flush()

    def assign(self, shift: Shift, *, user_id: int) -> Shift:
        shift.staff_id = user_id
        shift.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return shift

    def has_overlapping_shift(
        self,
        start: datetime,
        end: datetime,
        *,
        user_id: int | None = None,
        exclude_id: int | None = None,
    ) -> bool:
        """
        AU-04 closed-interval overlap predicate:
            existing.start_time < new.end AND existing.end_time > new.start
        Uses the index on staff_id for performance.
        """
        conditions = [
            Shift.is_deleted == False,  # noqa: E712
            Shift.start_time < end,
            Shift.end_time > start,
        ]
        if user_id is not None:
            conditions.append(Shift.staff_id == user_id)
        if exclude_id is not None:
            conditions.append(Shift.id != exclude_id)

        stmt = select(Shift.id).where(and_(*conditions)).limit(1)
        return self._db.scalar(stmt) is not None

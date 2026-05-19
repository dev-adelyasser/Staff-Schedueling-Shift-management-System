"""
app/repositories/availability_repository.py
────────────────────────────────────────────
DB queries for staff_availability — Slice 4.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.availability import StaffAvailability
from app.schemas.availability import AvailabilityCreateSchema


class AvailabilityRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_staff_and_day(
        self, staff_id: int, day_of_week: int
    ) -> StaffAvailability | None:
        stmt = select(StaffAvailability).where(
            StaffAvailability.staff_id == staff_id,
            StaffAvailability.day_of_week == day_of_week,
        )
        return self._db.scalars(stmt).one_or_none()

    def list_for_staff(self, staff_id: int) -> list[StaffAvailability]:
        stmt = select(StaffAvailability).where(
            StaffAvailability.staff_id == staff_id
        )
        return list(self._db.scalars(stmt))

    def upsert(
        self,
        staff_id: int,
        payload: AvailabilityCreateSchema,
    ) -> StaffAvailability:
        existing = self.get_by_staff_and_day(staff_id, payload.day_of_week)
        if existing:
            existing.start_time = payload.start_time
            existing.end_time = payload.end_time
            existing.is_available = payload.is_available
            self._db.flush()
            return existing
        record = StaffAvailability(
            staff_id=staff_id,
            day_of_week=payload.day_of_week,
            start_time=payload.start_time,
            end_time=payload.end_time,
            is_available=payload.is_available,
        )
        self._db.add(record)
        self._db.flush()
        return record

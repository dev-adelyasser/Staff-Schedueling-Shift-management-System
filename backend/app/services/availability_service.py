"""
app/services/availability_service.py
──────────────────────────────────────
Business logic for the Staff Availability slice (Slice 4).
"""

from sqlalchemy.orm import Session

from app.repositories.availability_repository import AvailabilityRepository
from app.schemas.availability import AvailabilityCreateSchema, AvailabilityResponseSchema


class AvailabilityService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = AvailabilityRepository(db)

    def set_availability(
        self,
        staff_id: int,
        payload: AvailabilityCreateSchema,
    ) -> AvailabilityResponseSchema:
        record = self._repo.upsert(staff_id, payload)
        return AvailabilityResponseSchema.model_validate(record)

    def get_availability(self, staff_id: int) -> list[AvailabilityResponseSchema]:
        rows = self._repo.list_for_staff(staff_id)
        return [AvailabilityResponseSchema.model_validate(r) for r in rows]

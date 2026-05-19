"""
app/services/attendance_service.py
────────────────────────────────────
Business logic for Clock In / Clock Out — Slice 5 (UC-06).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.attendance import AttendanceStatus
from app.repositories.attendance_repository import AttendanceRepository
from app.schemas.attendance import AttendanceResponseSchema


class AttendanceAlreadyClockedInError(Exception):
    pass


class AttendanceNotClockedInError(Exception):
    pass


class AttendanceRecordNotFoundError(Exception):
    pass


class AttendanceService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = AttendanceRepository(db)

    def clock_in(
        self,
        staff_id: int,
        shift_id: uuid.UUID | None,
    ) -> AttendanceResponseSchema:
        # Prevent double clock-in
        open_session = self._repo.get_open_session(staff_id)
        if open_session is not None:
            raise AttendanceAlreadyClockedInError(
                "Already clocked in — clock out first."
            )

        now = datetime.now(timezone.utc)
        record = self._repo.clock_in(staff_id, shift_id, clock_in=now)
        return AttendanceResponseSchema.model_validate(record)

    def clock_out(
        self,
        staff_id: int,
        record_id: uuid.UUID,
    ) -> AttendanceResponseSchema:
        record = self._repo.get(record_id)
        if record is None or record.staff_id != staff_id:
            raise AttendanceRecordNotFoundError(str(record_id))
        if record.clock_out is not None:
            raise AttendanceNotClockedInError("Already clocked out.")

        now = datetime.now(timezone.utc)
        # TODO: derive AttendanceStatus by comparing clock_in to shift.start_time
        status = AttendanceStatus.ON_TIME
        updated = self._repo.clock_out(record, clock_out=now, status=status)
        return AttendanceResponseSchema.model_validate(updated)

    def my_history(self, staff_id: int) -> list[AttendanceResponseSchema]:
        rows = self._repo.list_for_staff(staff_id)
        return [AttendanceResponseSchema.model_validate(r) for r in rows]

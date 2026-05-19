"""
app/repositories/attendance_repository.py
──────────────────────────────────────────
DB queries for attendance_records — Slice 5 (Clock In/Out).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord, AttendanceStatus


class AttendanceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, record_id: uuid.UUID) -> AttendanceRecord | None:
        return self._db.get(AttendanceRecord, record_id)

    def get_open_session(self, staff_id: int) -> AttendanceRecord | None:
        """Return the most recent un-clocked-out record for this staff member."""
        stmt = (
            select(AttendanceRecord)
            .where(
                and_(
                    AttendanceRecord.staff_id == staff_id,
                    AttendanceRecord.clock_out.is_(None),
                )
            )
            .order_by(AttendanceRecord.clock_in.desc())
            .limit(1)
        )
        return self._db.scalars(stmt).one_or_none()

    def list_for_staff(self, staff_id: int) -> list[AttendanceRecord]:
        stmt = (
            select(AttendanceRecord)
            .where(AttendanceRecord.staff_id == staff_id)
            .order_by(AttendanceRecord.clock_in.desc())
        )
        return list(self._db.scalars(stmt))

    def clock_in(
        self,
        staff_id: int,
        shift_id: uuid.UUID | None,
        *,
        clock_in: datetime,
    ) -> AttendanceRecord:
        record = AttendanceRecord(
            staff_id=staff_id,
            shift_id=shift_id,
            clock_in=clock_in,
        )
        self._db.add(record)
        self._db.flush()
        return record

    def clock_out(
        self,
        record: AttendanceRecord,
        *,
        clock_out: datetime,
        status: AttendanceStatus | None,
    ) -> AttendanceRecord:
        record.clock_out = clock_out
        record.status = status
        self._db.flush()
        return record

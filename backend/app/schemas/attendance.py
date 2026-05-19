"""
app/schemas/attendance.py
─────────────────────────
Schema contracts for Clock In/Out — Slice 5 (UC-06).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.attendance import AttendanceStatus


class ClockInSchema(BaseModel):
    """POST /api/v1/attendance/clock-in."""

    shift_id: uuid.UUID | None = None


class ClockOutSchema(BaseModel):
    """POST /api/v1/attendance/clock-out."""

    record_id: uuid.UUID


class AttendanceResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    staff_id: int
    shift_id: uuid.UUID | None
    clock_in: datetime
    clock_out: datetime | None
    status: AttendanceStatus | None
    created_at: datetime

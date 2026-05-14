"""
app/schemas/shift.py
────────────────────
Pydantic v2 schemas for the Shift resource.

All time fields are timezone-aware datetimes.
Padlock constraints (duration, rest period) are enforced in the
service layer, not here, to keep schemas declarative.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.validators import ShiftStatus, ShiftLimits


# ══════════════════════════════════════════════════════════════
#  Request Schemas
# ══════════════════════════════════════════════════════════════

class ShiftCreate(BaseModel):
    user_id:    int       = Field(..., gt=0)
    title:      str       = Field(..., min_length=1, max_length=255)
    start_time: datetime
    end_time:   datetime
    notes:      str | None = None
    schedule_id: int | None = None

    @model_validator(mode="after")
    def end_after_start(self) -> "ShiftCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class ShiftUpdate(BaseModel):
    title:      str | None       = Field(None, min_length=1, max_length=255)
    start_time: datetime | None  = None
    end_time:   datetime | None  = None
    notes:      str | None       = None
    status:     ShiftStatus | None = None
    schedule_id: int | None      = None


class ShiftStatusUpdate(BaseModel):
    """Dedicated schema for status-only transitions."""
    status: ShiftStatus


# ══════════════════════════════════════════════════════════════
#  Response Schemas
# ══════════════════════════════════════════════════════════════

class ShiftResponse(BaseModel):
    id:          int
    user_id:     int
    title:       str
    start_time:  datetime
    end_time:    datetime
    notes:       str | None
    status:      ShiftStatus
    schedule_id: int | None
    created_at:  datetime
    updated_at:  datetime

    model_config = ConfigDict(from_attributes=True)

"""
app/schemas/schedule.py
───────────────────────
Pydantic v2 schemas for the Schedule resource.
"""

from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.shift import ShiftResponse


class ScheduleCreate(BaseModel):
    name:        str       = Field(..., min_length=1, max_length=255)
    description: str | None = None
    week_start:  date
    week_end:    date

    @model_validator(mode="after")
    def end_after_start(self) -> "ScheduleCreate":
        if self.week_end <= self.week_start:
            raise ValueError("week_end must be after week_start.")
        return self


class ScheduleUpdate(BaseModel):
    name:        str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    week_start:  date | None = None
    week_end:    date | None = None


class ScheduleResponse(BaseModel):
    id:          int
    name:        str
    description: str | None
    week_start:  date
    week_end:    date
    created_by:  int | None
    created_at:  datetime
    updated_at:  datetime
    shifts:      list[ShiftResponse] = []

    model_config = ConfigDict(from_attributes=True)

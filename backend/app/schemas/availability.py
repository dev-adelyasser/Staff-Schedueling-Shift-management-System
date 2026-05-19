"""
app/schemas/availability.py
────────────────────────────
Schema contracts for the Staff Availability slice (Slice 4).
"""

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import Any


class AvailabilityCreateSchema(BaseModel):
    """
    PUT/POST /api/v1/availability.

    day_of_week: 0 = Monday … 6 = Sunday.
    start_time must be before end_time.
    """

    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool = True

    @field_validator("day_of_week")
    @classmethod
    def _valid_day(cls, v: int) -> int:
        if v not in range(7):
            raise ValueError("day_of_week must be 0–6 (Mon–Sun)")
        return v

    @model_validator(mode="before")
    @classmethod
    def _start_before_end(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        start = values.get("start_time")
        end = values.get("end_time")
        if start and end and end <= start:
            raise ValueError("end_time must be after start_time")
        return values


class AvailabilityResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    staff_id: int
    day_of_week: int
    start_time: time
    end_time: time
    is_available: bool
    created_at: datetime
    updated_at: datetime

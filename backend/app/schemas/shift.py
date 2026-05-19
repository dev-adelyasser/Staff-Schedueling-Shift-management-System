"""
app/schemas/shift.py
────────────────────
Public schema contracts for the Shift slice.

ShiftCreateSchema  — exactly 5 fields (spec §10); enforces start < end (HR-05).
ShiftResponseSchema — exactly 7 public fields; never exposes created_by,
                      updated_at, or is_deleted.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ShiftCreateSchema(BaseModel):
    """POST /api/v1/shifts — exactly 5 fields (spec §10)."""

    title: str
    start_time: datetime
    end_time: datetime
    department_id: int
    headcount: int = 1

    @model_validator(mode="before")
    @classmethod
    def _enforce_start_before_end(cls, values: Any) -> Any:
        """HR-05: start_time >= end_time → HTTP 422."""
        if not isinstance(values, dict):
            return values
        start = values.get("start_time")
        end = values.get("end_time")
        if start is None or end is None:
            return values
        # Convert strings so the comparison works regardless of input form.
        if isinstance(start, str):
            start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if isinstance(end, str):
            end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        if end <= start:
            raise ValueError("end_time must be strictly after start_time")
        return values

    @field_validator("headcount")
    @classmethod
    def _headcount_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("headcount must be >= 1")
        return v


class ShiftResponseSchema(BaseModel):
    """Public representation — 7 fields only (spec §10)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    start_time: datetime
    end_time: datetime
    department_id: int
    headcount: int
    created_at: datetime


class ShiftListResponseSchema(BaseModel):
    """Paginated wrapper returned by GET /api/v1/shifts."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ShiftResponseSchema]
    total: int
    skip: int
    limit: int


class BulkUploadResultSchema(BaseModel):
    """Response for POST /api/v1/shifts/bulk-upload."""

    created: list[ShiftResponseSchema]
    errors: list[dict[str, Any]]

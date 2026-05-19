"""
app/schemas/swap.py
───────────────────
Schema contracts for the Shift Swap workflow — Slice 6 (AU-08).
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.swap_request import SwapStatus


class SwapRequestCreateSchema(BaseModel):
    """
    POST /api/v1/swaps.

    Constraints (spec):
      - requester_shift_id must NOT equal target_shift_id.
      - reason is optional, max 500 chars.
    """

    requester_shift_id: uuid.UUID
    target_shift_id: uuid.UUID
    reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _shifts_must_differ(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        if values.get("requester_shift_id") == values.get("target_shift_id"):
            raise ValueError("requester_shift_id and target_shift_id must be different")
        return values

    @field_validator("reason")
    @classmethod
    def _reason_max_len(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 500:
            raise ValueError("reason must be 500 characters or fewer")
        return v


class SwapRequestResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: int
    requester_shift_id: uuid.UUID
    target_shift_id: uuid.UUID
    reason: str | None
    status: SwapStatus
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: int | None

"""
app/schemas/assignment.py
─────────────────────────
Schema contracts for POST /api/v1/shifts/{id}/assign.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssignmentCreateSchema(BaseModel):
    """Body for POST /api/v1/shifts/{id}/assign."""

    staff_id: int


class AssignmentResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shift_id: uuid.UUID
    staff_id: int
    assigned_by: int | None
    assigned_at: datetime

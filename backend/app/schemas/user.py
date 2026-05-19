from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserCreateSchema(BaseModel):
    """Inbound payload for registering a new user (FR-02)."""

    email: EmailStr
    # AU-01 / AUTH-01: minimum 8 characters enforced at the schema boundary.
    # Upper-case, digit, and special-char requirements are enforced in the
    # service layer via core/validators.py (PasswordLimits).
    password: Annotated[str, Field(min_length=8)]
    role: UserRole = UserRole.STAFF


class UserUpdateSchema(BaseModel):
    """Inbound payload for updating a user record.

    id is required so the service can locate the target row unambiguously.
    Every other field is Optional — only supplied fields are applied.
    """

    id: int
    email: EmailStr | None = None
    password: Annotated[str, Field(min_length=8)] | None = None
    role: UserRole | None = None


class UserResponseSchema(BaseModel):
    """Outbound user representation — safe to serialise to the API caller.

    Invariants:
    • hashed_password is NEVER included (Information Hiding / AU-02).
    • token_version is NEVER included (internal HR-04 implementation detail).
    """

    id: int
    email: EmailStr
    role: UserRole
    is_deleted: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

"""
app/schemas/user.py
───────────────────
Pydantic v2 schemas that define the PUBLIC API contract for the User resource.

Information Hiding guarantee
────────────────────────────
• `hashed_password` is NEVER included in any response schema.
• Internal DB fields (e.g. raw IDs for joins) are mapped to friendly names.
• Route handlers only import from `app/schemas/`, never from `app/models/`.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.validators import UserRole, validate_password, validate_email


# ══════════════════════════════════════════════════════════════
#  Request Schemas  (inbound payloads)
# ══════════════════════════════════════════════════════════════

class UserCreate(BaseModel):
    """Payload required to register a new user."""

    email: EmailStr = Field(..., description="Must be a valid email address.")
    full_name: str  = Field(..., min_length=2, max_length=255)
    password: str   = Field(..., description="Must pass complexity Padlock AUTH-01.")
    role: UserRole  = Field(UserRole.STAFF, description="Defaults to 'staff'.")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        return validate_password(v)   # ← delegates to Padlock AUTH-01

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return validate_email(v)      # ← delegates to Padlock AUTH-02


class UserUpdate(BaseModel):
    """All fields optional – PATCH semantics."""

    full_name: str | None = Field(None, min_length=2, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None  = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_password(v)
        return v


# ══════════════════════════════════════════════════════════════
#  Response Schemas  (outbound – zero DB leakage)
# ══════════════════════════════════════════════════════════════

class UserPublic(BaseModel):
    """Safe, minimal representation returned in lists / embeds."""

    id: int
    full_name: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """Full user response – NO hashed_password field."""

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ══════════════════════════════════════════════════════════════
#  Auth Schemas
# ══════════════════════════════════════════════════════════════

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

"""
app/schemas/__init__.py
───────────────────────
Re-exports all public schema contracts.
Routers import from here; never from individual schema modules.
"""

from app.schemas.user import (  # noqa: F401
    UserCreate, UserUpdate, UserPublic, UserResponse,
    TokenResponse, LoginRequest,
)
from app.schemas.shift import (  # noqa: F401
    ShiftCreate, ShiftUpdate, ShiftStatusUpdate, ShiftResponse,
)
from app.schemas.schedule import (  # noqa: F401
    ScheduleCreate, ScheduleUpdate, ScheduleResponse,
)

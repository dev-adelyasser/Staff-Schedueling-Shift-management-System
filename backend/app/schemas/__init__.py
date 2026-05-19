"""
app/schemas/__init__.py
──────────────────────
Public schema registry — routers import from here.
"""

from app.schemas.user import (  # noqa: F401
    UserCreateSchema,
    UserUpdateSchema,
    UserResponseSchema,
)
from app.schemas.auth import (  # noqa: F401
    LoginRequest,
    TokenSchema,
)
from app.schemas.shift import (  # noqa: F401
    ShiftCreateSchema,
    ShiftResponseSchema,
)
from app.schemas.assignment import (  # noqa: F401
    AssignmentCreateSchema,
    AssignmentResponseSchema,
)
from app.schemas.swap import (  # noqa: F401
    SwapRequestCreateSchema,
    SwapRequestResponseSchema,
)
from app.schemas.availability import (  # noqa: F401
    AvailabilityCreateSchema,
    AvailabilityResponseSchema,
)
from app.schemas.attendance import (  # noqa: F401
    AttendanceResponseSchema,
)

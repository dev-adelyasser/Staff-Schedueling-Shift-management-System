"""
app/models/__init__.py
──────────────────────
Centralised model registry.

Importing this package registers every ORM model on the single shared
Base.metadata so Alembic autogenerate and test helpers see all tables.
Import order matters for FK resolution: User first, then dependent tables.
"""

from app.models.user import User                           # noqa: F401
from app.models.schedule import Schedule                   # noqa: F401
from app.models.shift import Shift                         # noqa: F401
from app.models.staff_assignment import StaffAssignment    # noqa: F401
from app.models.audit_log import AuditLog                  # noqa: F401
from app.models.swap_request import SwapRequest            # noqa: F401
from app.models.availability import StaffAvailability      # noqa: F401
from app.models.attendance import AttendanceRecord         # noqa: F401

__all__ = [
    "User",
    "Schedule",
    "Shift",
    "StaffAssignment",
    "AuditLog",
    "SwapRequest",
    "StaffAvailability",
    "AttendanceRecord",
]

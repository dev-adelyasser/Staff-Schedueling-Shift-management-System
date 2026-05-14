"""
app/models/__init__.py
──────────────────────
Centralised model registry.

Importing this package ensures every ORM model is registered
with SQLAlchemy's metadata before any migration or table-creation
call.  Never import individual model files directly from outside
the models package – use this entry point.
"""

from app.models.user import User          # noqa: F401
from app.models.shift import Shift        # noqa: F401
from app.models.schedule import Schedule  # noqa: F401

__all__ = ["User", "Shift", "Schedule"]

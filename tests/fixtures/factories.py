"""
tests/fixtures/factories.py
────────────────────────────
Factory-Boy model factories for generating test data.

Usage:
    from tests.fixtures.factories import UserFactory, ShiftFactory

    user  = UserFactory.build()            # ORM object, not saved
    user  = UserFactory.create(db=session) # saved to test DB

These factories feed the Testing Pyramid at all three levels.
"""

from datetime import datetime, timedelta, timezone
from app.core.security import hash_password
from app.core.validators import UserRole, ShiftStatus
from app.models.user import User
from app.models.shift import Shift


class UserFactory:
    """Builds User ORM instances with sensible defaults."""

    _counter = 0

    @classmethod
    def _next(cls) -> int:
        cls._counter += 1
        return cls._counter

    @classmethod
    def build(
        cls,
        *,
        email: str | None = None,
        full_name: str = "Test User",
        role: UserRole = UserRole.STAFF,
        is_active: bool = True,
        password: str = "Test@12345",
    ) -> User:
        n = cls._next()
        return User(
            id=n,
            email=email or f"user{n}@example.com",
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role,
            is_active=is_active,
        )

    @classmethod
    def create(cls, db, **kwargs) -> User:
        user = cls.build(**kwargs)
        user.id = None  # let DB assign
        db.add(user)
        db.flush()
        return user


class ShiftFactory:
    """Builds Shift ORM instances with sensible defaults."""

    @staticmethod
    def build(
        *,
        user_id: int = 1,
        start_offset_hours: int = 0,
        duration_hours: int = 8,
        title: str = "Morning Shift",
        status: ShiftStatus = ShiftStatus.DRAFT,
    ) -> Shift:
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        start = now + timedelta(hours=start_offset_hours)
        end   = start + timedelta(hours=duration_hours)
        return Shift(
            user_id=user_id,
            title=title,
            start_time=start,
            end_time=end,
            status=status,
        )

    @classmethod
    def create(cls, db, **kwargs) -> Shift:
        shift = cls.build(**kwargs)
        db.add(shift)
        db.flush()
        return shift

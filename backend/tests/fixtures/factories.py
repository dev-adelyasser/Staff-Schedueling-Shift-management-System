"""
backend/tests/fixtures/factories.py
──────────────────────────────────────
factory-boy 3.3.0 factories for Person 2's test models.

All factories are SQLAlchemy-backed. Pass `_session=<db_session>` when
using integration tests; unit tests build instances without a session.
"""

import uuid
from datetime import datetime, timedelta, timezone

import factory
from factory.alchemy import SQLAlchemyModelFactory

from app.core.security import hash_password
from app.models.attendance import AttendanceRecord, AttendanceStatus
from app.models.shift import Shift
from app.models.staff_assignment import StaffAssignment
from app.models.swap_request import SwapRequest, SwapStatus
from app.models.user import User, UserRole


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "flush"

    id = factory.Sequence(lambda n: n + 1)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    hashed_password = factory.LazyFunction(lambda: hash_password("Password1!"))
    role = UserRole.STAFF
    is_active = True
    is_deleted = False
    token_version = 1


class AdminFactory(UserFactory):
    role = UserRole.ADMIN
    email = factory.Sequence(lambda n: f"admin{n}@example.com")


class ShiftFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Shift
        sqlalchemy_session_persistence = "flush"

    id = factory.LazyFunction(uuid.uuid4)
    title = factory.Sequence(lambda n: f"Shift {n}")
    start_time = factory.LazyFunction(
        lambda: datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        + timedelta(hours=1)
    )
    end_time = factory.LazyAttribute(lambda o: o.start_time + timedelta(hours=8))
    department_id = 1
    headcount = 1
    is_deleted = False


class StaffAssignmentFactory(SQLAlchemyModelFactory):
    class Meta:
        model = StaffAssignment
        sqlalchemy_session_persistence = "flush"

    shift = factory.SubFactory(ShiftFactory)
    staff_id = factory.Sequence(lambda n: n + 100)
    assigned_by = None


class SwapRequestFactory(SQLAlchemyModelFactory):
    class Meta:
        model = SwapRequest
        sqlalchemy_session_persistence = "flush"

    id = factory.LazyFunction(uuid.uuid4)
    requester_id = factory.Sequence(lambda n: n + 1)
    requester_shift_id = factory.LazyFunction(uuid.uuid4)
    target_shift_id = factory.LazyFunction(uuid.uuid4)
    reason = "Need to swap due to personal conflict"
    status = SwapStatus.PENDING

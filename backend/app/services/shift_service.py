"""
app/services/shift_service.py
──────────────────────────────
Business logic for Shift scheduling.

Every write operation passes through Padlock validators FIRST,
ensuring constraints can never be bypassed by a direct repo call.
"""

from datetime import timedelta
from sqlalchemy.orm import Session

from app.core.validators import (
    validate_shift_duration,
    validate_rest_period,
    validate_weekly_hours,
    require_permission,
    UserRole,
)
from app.models.shift import Shift
from app.repositories.shift_repository import ShiftRepository
from app.schemas.shift import ShiftCreate, ShiftUpdate


class ShiftNotFoundError(Exception):
    pass


class ShiftService:

    def __init__(self, db: Session) -> None:
        self._repo = ShiftRepository(db)

    def create_shift(self, payload: ShiftCreate, *, actor_role: UserRole) -> Shift:
        require_permission(actor_role, UserRole.MANAGER)  # Padlock ROLE-03

        # Padlock SHIFT-01: duration bounds
        validate_shift_duration(payload.start_time, payload.end_time)

        # Padlock SHIFT-02: rest period from last shift
        last = self._repo.get_last_shift_for_user(payload.user_id)
        if last:
            validate_rest_period(last.end_time, payload.start_time)

        # Padlock SHIFT-03: weekly hour cap
        week_start = payload.start_time - timedelta(days=payload.start_time.weekday())
        week_end   = week_start + timedelta(days=7)
        existing   = self._repo.list_by_user_in_window(
            payload.user_id, week_start, week_end
        )
        total_hrs = sum(
            (s.end_time - s.start_time).total_seconds() / 3600 for s in existing
        )
        new_hrs = (payload.end_time - payload.start_time).total_seconds() / 3600
        validate_weekly_hours(total_hrs + new_hrs)

        return self._repo.create(**payload.model_dump())

    def get_shift(self, shift_id: int) -> Shift:
        shift = self._repo.get_by_id(shift_id)
        if not shift:
            raise ShiftNotFoundError(f"Shift {shift_id} not found.")
        return shift

    def list_shifts(self, *, skip: int = 0, limit: int = 100) -> list[Shift]:
        return self._repo.list_all(skip=skip, limit=limit)

    def list_user_shifts(self, user_id: int) -> list[Shift]:
        return self._repo.list_by_user(user_id)

    def update_shift(
        self, shift_id: int, payload: ShiftUpdate, *, actor_role: UserRole
    ) -> Shift:
        require_permission(actor_role, UserRole.MANAGER)
        shift = self.get_shift(shift_id)

        updates = payload.model_dump(exclude_none=True)

        # Re-validate duration if times are changing
        start = updates.get("start_time", shift.start_time)
        end   = updates.get("end_time",   shift.end_time)
        if "start_time" in updates or "end_time" in updates:
            validate_shift_duration(start, end)

        return self._repo.update(shift, **updates)

    def delete_shift(self, shift_id: int, *, actor_role: UserRole) -> None:
        require_permission(actor_role, UserRole.ADMIN)
        shift = self.get_shift(shift_id)
        self._repo.delete(shift)

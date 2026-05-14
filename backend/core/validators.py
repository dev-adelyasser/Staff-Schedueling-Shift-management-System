"""
app/core/validators.py
──────────────────────
❰ EDGE CASE CAGE ❱ — Padlock Constraint Library

All boundary conditions and threshold rules for the Staff Scheduling System
are defined here as named, testable pure functions.

Design principles
─────────────────
  • Every Padlock is a PURE FUNCTION: no DB I/O, no HTTP, no side effects.
  • Constants are READ FROM settings so thresholds can be overridden via .env.
  • Each Padlock raises a typed domain exception (never a generic ValueError).
  • Services call Padlocks BEFORE any DB write — the cage is always closed.

Padlock catalogue
──────────────────
  ID          Function                      Constraint
  ──────────  ──────────────────────────── ────────────────────────────────────
  SHIFT-01    validate_shift_duration       min ≤ duration ≤ max hours
  SHIFT-02    validate_rest_period          ≥ min_rest_hours between shifts
  SHIFT-03    validate_weekly_hours         ≤ max_weekly_hours in 7-day window
  SHIFT-04    requires_break                advisory: break if ≥ threshold hours
  SCHEDULE-01 validate_roster_size          ≤ max_users_per_schedule
  ROLE-01     validate_role                 must be a valid UserRole enum member
  ROLE-02     validate_role_elevation       no privilege escalation
  ROLE-03     has_permission                actor meets minimum role level
  ROLE-04     require_permission            raises if ROLE-03 fails
  AUTH-01     validate_password             complexity: length, case, digit, special
  AUTH-02     validate_email                structural email format

Testing target: 70 % of the test suite covers this module (unit layer).
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Final

from app.core.config import settings


# ══════════════════════════════════════════════════════════════════════════════
#  Domain Enumerations
# ══════════════════════════════════════════════════════════════════════════════

class UserRole(str, Enum):
    ADMIN   = "admin"
    MANAGER = "manager"
    STAFF   = "staff"
    VIEWER  = "viewer"


class ShiftStatus(str, Enum):
    DRAFT     = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"


# ══════════════════════════════════════════════════════════════════════════════
#  Threshold Constants — sourced from settings (config-driven Padlocks)
#  Declared as module-level constants so tests can assert against them.
# ══════════════════════════════════════════════════════════════════════════════

class ShiftLimits:
    """Threshold constants for shift duration constraints (Padlock SHIFT-01/02/03/04)."""
    MIN_HOURS:         Final[float] = settings.shift_min_duration_hours
    MAX_HOURS:         Final[float] = settings.shift_max_duration_hours
    MAX_WEEKLY_HOURS:  Final[float] = settings.max_weekly_hours_per_user
    MIN_REST_HOURS:    Final[float] = settings.min_rest_hours_between_shifts
    BREAK_THRESHOLD:   Final[float] = settings.shift_break_threshold_hours
    MAX_PER_WEEK:      Final[int]   = settings.max_shifts_per_user_per_week


class ScheduleLimits:
    """Threshold constants for schedule/roster constraints (Padlock SCHEDULE-01)."""
    MAX_USERS_PER_SCHEDULE: Final[int] = settings.max_users_per_schedule


class PasswordLimits:
    """Threshold constants for password complexity (Padlock AUTH-01)."""
    MIN_LENGTH:        Final[int]  = 8
    MAX_LENGTH:        Final[int]  = 128
    REQUIRE_UPPERCASE: Final[bool] = True
    REQUIRE_DIGIT:     Final[bool] = True
    REQUIRE_SPECIAL:   Final[bool] = True


class RoleLimits:
    """Role privilege hierarchy (Padlock ROLE-02/03/04). Higher = more privilege."""
    HIERARCHY: Final[dict[UserRole, int]] = {
        UserRole.VIEWER:  0,
        UserRole.STAFF:   1,
        UserRole.MANAGER: 2,
        UserRole.ADMIN:   3,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Domain Exceptions — typed, one per Padlock group
# ══════════════════════════════════════════════════════════════════════════════

class ValidationError(ValueError):
    """Base class for all Padlock violations."""


class ShiftValidationError(ValidationError):
    """Raised when shift constraints (SHIFT-01/02/03/04) are violated."""


class ScheduleValidationError(ValidationError):
    """Raised when schedule/roster constraints (SCHEDULE-01) are violated."""


class RoleValidationError(ValidationError):
    """Raised when role/permission constraints (ROLE-01/02/03/04) are violated."""


class PasswordValidationError(ValidationError):
    """Raised when password complexity rules (AUTH-01) are violated."""


class RestPeriodViolationError(ShiftValidationError):
    """Raised when minimum rest period between shifts (SHIFT-02) is not met."""


# ══════════════════════════════════════════════════════════════════════════════
#  SHIFT Padlocks
# ══════════════════════════════════════════════════════════════════════════════

def validate_shift_duration(start: datetime, end: datetime) -> float:
    """
    Padlock ❰SHIFT-01❱ — shift duration must be within configured bounds.

    Args:
        start: timezone-aware shift start datetime.
        end:   timezone-aware shift end datetime.

    Returns:
        Duration in decimal hours (e.g. 8.5 for 8h 30m).

    Raises:
        ShiftValidationError: if end ≤ start, or duration out of [MIN, MAX].
    """
    if end <= start:
        raise ShiftValidationError(
            f"Shift end ({end.isoformat()}) must be strictly after "
            f"start ({start.isoformat()})."
        )

    duration_hours = (end - start).total_seconds() / 3600.0

    if duration_hours < ShiftLimits.MIN_HOURS:
        raise ShiftValidationError(
            f"Shift duration {duration_hours:.2f}h is below the minimum "
            f"of {ShiftLimits.MIN_HOURS}h. "
            f"Adjust SHIFT_MIN_DURATION_HOURS in .env to change this threshold."
        )

    if duration_hours > ShiftLimits.MAX_HOURS:
        raise ShiftValidationError(
            f"Shift duration {duration_hours:.2f}h exceeds the maximum "
            f"of {ShiftLimits.MAX_HOURS}h. "
            f"Adjust SHIFT_MAX_DURATION_HOURS in .env to change this threshold."
        )

    return duration_hours


def validate_rest_period(previous_end: datetime, next_start: datetime) -> None:
    """
    Padlock ❰SHIFT-02❱ — enforce minimum rest between consecutive shifts.

    Args:
        previous_end: end of the preceding shift.
        next_start:   start of the proposed new shift.

    Raises:
        RestPeriodViolationError: if gap < MIN_REST_HOURS.
    """
    gap_hours = (next_start - previous_end).total_seconds() / 3600.0

    if gap_hours < ShiftLimits.MIN_REST_HOURS:
        raise RestPeriodViolationError(
            f"Only {gap_hours:.1f}h rest between shifts; "
            f"minimum required is {ShiftLimits.MIN_REST_HOURS}h "
            f"(configured via MIN_REST_HOURS_BETWEEN_SHIFTS)."
        )


def validate_weekly_hours(total_hours: float) -> None:
    """
    Padlock ❰SHIFT-03❱ — weekly working hours must not exceed configured cap.

    Args:
        total_hours: sum of shift durations in the rolling 7-day window
                     (including the proposed new shift).

    Raises:
        ShiftValidationError: if total_hours > MAX_WEEKLY_HOURS.
    """
    if total_hours > ShiftLimits.MAX_WEEKLY_HOURS:
        raise ShiftValidationError(
            f"Weekly total of {total_hours:.1f}h exceeds the maximum "
            f"of {ShiftLimits.MAX_WEEKLY_HOURS}h "
            f"(configured via MAX_WEEKLY_HOURS_PER_USER)."
        )


def validate_weekly_shift_count(shift_count: int) -> None:
    """
    Padlock ❰SHIFT-03b❱ — number of shifts per week must not exceed cap.

    Args:
        shift_count: number of shifts already scheduled in the week
                     PLUS the proposed new shift.

    Raises:
        ShiftValidationError: if shift_count > MAX_PER_WEEK.
    """
    if shift_count > ShiftLimits.MAX_PER_WEEK:
        raise ShiftValidationError(
            f"Shift count {shift_count} exceeds the maximum of "
            f"{ShiftLimits.MAX_PER_WEEK} shifts per week "
            f"(configured via MAX_SHIFTS_PER_USER_PER_WEEK)."
        )


def requires_break(duration_hours: float) -> bool:
    """
    Padlock ❰SHIFT-04❱ — advisory: is a mandatory break required?

    Returns:
        True if a break must be scheduled (duration ≥ BREAK_THRESHOLD).
        This is non-blocking; callers log a warning and may add a break record.
    """
    return duration_hours >= ShiftLimits.BREAK_THRESHOLD


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULE Padlocks
# ══════════════════════════════════════════════════════════════════════════════

def validate_roster_size(current_count: int) -> None:
    """
    Padlock ❰SCHEDULE-01❱ — schedule roster must not exceed configured cap.

    Args:
        current_count: number of users ALREADY in the schedule
                       PLUS the user being added.

    Raises:
        ScheduleValidationError: if current_count > MAX_USERS_PER_SCHEDULE.
    """
    if current_count > ScheduleLimits.MAX_USERS_PER_SCHEDULE:
        raise ScheduleValidationError(
            f"Roster size {current_count} exceeds the maximum of "
            f"{ScheduleLimits.MAX_USERS_PER_SCHEDULE} users per schedule "
            f"(configured via MAX_USERS_PER_SCHEDULE)."
        )


# ══════════════════════════════════════════════════════════════════════════════
#  ROLE Padlocks
# ══════════════════════════════════════════════════════════════════════════════

def validate_role(value: str) -> UserRole:
    """
    Padlock ❰ROLE-01❱ — value must be a valid UserRole member.

    Returns:
        The corresponding UserRole enum member (normalised to lowercase).

    Raises:
        RoleValidationError: for unknown role strings.
    """
    try:
        return UserRole(value.lower())
    except ValueError:
        valid = [r.value for r in UserRole]
        raise RoleValidationError(
            f"'{value}' is not a valid role. Allowed values: {valid}."
        )


def validate_role_elevation(
    requesting_role: UserRole,
    target_role: UserRole,
) -> None:
    """
    Padlock ❰ROLE-02❱ — prevent privilege escalation.

    A user cannot assign a role equal to or higher than their own.

    Args:
        requesting_role: the role of the user performing the assignment.
        target_role:     the role they are trying to assign.

    Raises:
        RoleValidationError: if target_role ≥ requesting_role in hierarchy.
    """
    req_level = RoleLimits.HIERARCHY[requesting_role]
    tgt_level = RoleLimits.HIERARCHY[target_role]

    if tgt_level >= req_level:
        raise RoleValidationError(
            f"A '{requesting_role.value}' cannot assign the "
            f"'{target_role.value}' role — privilege escalation denied. "
            f"({req_level} cannot assign level {tgt_level}.)"
        )


def has_permission(actor_role: UserRole, minimum_role: UserRole) -> bool:
    """
    Padlock ❰ROLE-03❱ — check whether actor meets the minimum role requirement.

    Returns:
        True if actor's level ≥ minimum_role's level.
    """
    return RoleLimits.HIERARCHY[actor_role] >= RoleLimits.HIERARCHY[minimum_role]


def require_permission(actor_role: UserRole, minimum_role: UserRole) -> None:
    """
    Padlock ❰ROLE-04❱ — raise if actor does not meet the minimum role.

    Raises:
        RoleValidationError: listing the required and actual roles.
    """
    if not has_permission(actor_role, minimum_role):
        raise RoleValidationError(
            f"Action requires at least '{minimum_role.value}' role; "
            f"actor has '{actor_role.value}'."
        )


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH Padlocks
# ══════════════════════════════════════════════════════════════════════════════

def validate_password(password: str) -> str:
    """
    Padlock ❰AUTH-01❱ — enforce password complexity rules.

    All failing rules are collected and reported together so the user can
    fix all issues in one attempt (not one error at a time).

    Returns:
        The original password string if all rules pass.

    Raises:
        PasswordValidationError: listing every failing rule.
    """
    errors: list[str] = []

    if len(password) < PasswordLimits.MIN_LENGTH:
        errors.append(f"At least {PasswordLimits.MIN_LENGTH} characters required.")

    if len(password) > PasswordLimits.MAX_LENGTH:
        errors.append(f"Must not exceed {PasswordLimits.MAX_LENGTH} characters.")

    if PasswordLimits.REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        errors.append("At least one uppercase letter required.")

    if PasswordLimits.REQUIRE_DIGIT and not re.search(r"\d", password):
        errors.append("At least one digit required.")

    if PasswordLimits.REQUIRE_SPECIAL and not re.search(
        r"[!@#$%^&*()\-_=+\[\]{}|;:'\",.<>?/]", password
    ):
        errors.append("At least one special character required.")

    if errors:
        raise PasswordValidationError(
            "Password does not meet complexity requirements: "
            + " | ".join(errors)
        )

    return password


_EMAIL_RE: re.Pattern[str] = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def validate_email(email: str) -> str:
    """
    Padlock ❰AUTH-02❱ — structural email validation and normalisation.

    Returns:
        Normalised (lowercased, stripped) email address.

    Raises:
        ValidationError: for structurally invalid addresses.
    """
    normalised = email.strip().lower()
    if not _EMAIL_RE.match(normalised):
        raise ValidationError(
            f"'{email}' is not a valid email address."
        )
    return normalised

"""
app/core/validators.py
──────────────────────
❰ EDGE CASE CAGE ❱  –  Padlock Constraints

This module is the single source of truth for ALL boundary conditions,
threshold limits, and role-permission rules in the system.

Design pattern: each Padlock is a pure function (no DB I/O) that raises
a domain-specific exception or returns a validated value.  Services call
these BEFORE persisting any entity, ensuring the cage is always closed.

Testing pyramid target: 70 % of unit tests live here.
"""

from __future__ import annotations

import re
from datetime import time, timedelta, datetime
from enum import Enum
from typing import Final


# ══════════════════════════════════════════════════════════════
#  Domain Enumerations  (single definition – no duplication)
# ══════════════════════════════════════════════════════════════

class UserRole(str, Enum):
    ADMIN   = "admin"
    MANAGER = "manager"
    STAFF   = "staff"
    VIEWER  = "viewer"


class ShiftStatus(str, Enum):
    DRAFT     = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"


# ══════════════════════════════════════════════════════════════
#  Threshold Constants  (named, documented)
# ══════════════════════════════════════════════════════════════

class ShiftLimits:
    """Padlock: hard boundaries for shift durations."""

    MIN_HOURS: Final[float]  = 1.0    # Shortest legal shift
    MAX_HOURS: Final[float]  = 12.0   # Longest single shift (labour law proxy)
    MAX_WEEKLY_HOURS: Final[float] = 48.0  # EU Working Time Directive proxy
    MIN_REST_HOURS: Final[float]   = 11.0  # Mandatory rest between shifts
    BREAK_THRESHOLD_HOURS: Final[float] = 6.0  # Shift length that mandates a break


class PasswordLimits:
    """Padlock: password complexity thresholds."""

    MIN_LENGTH: Final[int] = 8
    MAX_LENGTH: Final[int] = 128
    REQUIRE_UPPERCASE: Final[bool] = True
    REQUIRE_DIGIT:     Final[bool] = True
    REQUIRE_SPECIAL:   Final[bool] = True
    SPECIAL_CHARS: Final[str] = r"!@#$%^&*()_+-=[]{}|;':\",./<>?"


class RoleLimits:
    """Padlock: role hierarchy ordinals (higher = more privilege)."""

    HIERARCHY: Final[dict[UserRole, int]] = {
        UserRole.VIEWER:  0,
        UserRole.STAFF:   1,
        UserRole.MANAGER: 2,
        UserRole.ADMIN:   3,
    }


# ══════════════════════════════════════════════════════════════
#  Domain Exceptions  (typed, descriptive)
# ══════════════════════════════════════════════════════════════

class ValidationError(ValueError):
    """Base class for all padlock violations."""


class ShiftValidationError(ValidationError):
    """Raised when shift constraints are violated."""


class RoleValidationError(ValidationError):
    """Raised when role/permission constraints are violated."""


class PasswordValidationError(ValidationError):
    """Raised when password complexity rules are violated."""


class RestPeriodViolationError(ShiftValidationError):
    """Raised when minimum rest period between shifts is not met."""


# ══════════════════════════════════════════════════════════════
#  Padlock Functions  –  Shift Constraints
# ══════════════════════════════════════════════════════════════

def validate_shift_duration(start: datetime, end: datetime) -> float:
    """
    Padlock ❰SHIFT-01❱: shift must be between MIN_HOURS and MAX_HOURS.

    Returns:
        Duration in hours (float).
    Raises:
        ShiftValidationError on any violation.
    """
    if end <= start:
        raise ShiftValidationError(
            f"Shift end ({end}) must be strictly after start ({start})."
        )

    duration_hours = (end - start).total_seconds() / 3600.0

    if duration_hours < ShiftLimits.MIN_HOURS:
        raise ShiftValidationError(
            f"Shift duration {duration_hours:.2f}h is below the minimum "
            f"of {ShiftLimits.MIN_HOURS}h."
        )

    if duration_hours > ShiftLimits.MAX_HOURS:
        raise ShiftValidationError(
            f"Shift duration {duration_hours:.2f}h exceeds the maximum "
            f"of {ShiftLimits.MAX_HOURS}h."
        )

    return duration_hours


def validate_rest_period(previous_end: datetime, next_start: datetime) -> None:
    """
    Padlock ❰SHIFT-02❱: enforce minimum rest between two consecutive shifts.

    Raises:
        RestPeriodViolationError if the gap is less than MIN_REST_HOURS.
    """
    gap_hours = (next_start - previous_end).total_seconds() / 3600.0

    if gap_hours < ShiftLimits.MIN_REST_HOURS:
        raise RestPeriodViolationError(
            f"Only {gap_hours:.1f}h rest between shifts; "
            f"minimum required is {ShiftLimits.MIN_REST_HOURS}h."
        )


def validate_weekly_hours(total_hours: float) -> None:
    """
    Padlock ❰SHIFT-03❱: a staff member may not exceed MAX_WEEKLY_HOURS
    in any rolling 7-day window.

    Args:
        total_hours: sum of all shift durations in the week (pre-computed).
    Raises:
        ShiftValidationError if the limit is breached.
    """
    if total_hours > ShiftLimits.MAX_WEEKLY_HOURS:
        raise ShiftValidationError(
            f"Weekly total of {total_hours:.1f}h exceeds the legal maximum "
            f"of {ShiftLimits.MAX_WEEKLY_HOURS}h."
        )


def requires_break(duration_hours: float) -> bool:
    """
    Padlock ❰SHIFT-04❱: advisory – returns True if a mandatory break
    must be scheduled within the shift.
    """
    return duration_hours >= ShiftLimits.BREAK_THRESHOLD_HOURS


# ══════════════════════════════════════════════════════════════
#  Padlock Functions  –  Role / Permission Constraints
# ══════════════════════════════════════════════════════════════

def validate_role(value: str) -> UserRole:
    """
    Padlock ❰ROLE-01❱: value must be a known UserRole member.

    Raises:
        RoleValidationError for unknown role strings.
    """
    try:
        return UserRole(value.lower())
    except ValueError:
        valid = [r.value for r in UserRole]
        raise RoleValidationError(
            f"'{value}' is not a valid role. Allowed: {valid}."
        )


def validate_role_elevation(requesting_role: UserRole, target_role: UserRole) -> None:
    """
    Padlock ❰ROLE-02❱: a user cannot assign a role equal to or higher
    than their own (privilege escalation guard).

    Args:
        requesting_role: the role of the user performing the assignment.
        target_role:     the role they are trying to assign.
    Raises:
        RoleValidationError if escalation is attempted.
    """
    req_level = RoleLimits.HIERARCHY[requesting_role]
    tgt_level = RoleLimits.HIERARCHY[target_role]

    if tgt_level >= req_level:
        raise RoleValidationError(
            f"A '{requesting_role.value}' cannot assign the "
            f"'{target_role.value}' role (privilege escalation denied)."
        )


def has_permission(actor_role: UserRole, minimum_role: UserRole) -> bool:
    """
    Padlock ❰ROLE-03❱: returns True if actor's privilege level meets
    or exceeds the required minimum.
    """
    return RoleLimits.HIERARCHY[actor_role] >= RoleLimits.HIERARCHY[minimum_role]


def require_permission(actor_role: UserRole, minimum_role: UserRole) -> None:
    """
    Padlock ❰ROLE-04❱: raises RoleValidationError if permission check fails.
    Convenience wrapper for use inside services / route guards.
    """
    if not has_permission(actor_role, minimum_role):
        raise RoleValidationError(
            f"Action requires at least '{minimum_role.value}' role; "
            f"actor has '{actor_role.value}'."
        )


# ══════════════════════════════════════════════════════════════
#  Padlock Functions  –  Password Complexity
# ══════════════════════════════════════════════════════════════

def validate_password(password: str) -> str:
    """
    Padlock ❰AUTH-01❱: enforce password complexity rules.

    Returns the original password if valid.
    Raises:
        PasswordValidationError listing all failures.
    """
    errors: list[str] = []

    if len(password) < PasswordLimits.MIN_LENGTH:
        errors.append(f"Must be at least {PasswordLimits.MIN_LENGTH} characters.")

    if len(password) > PasswordLimits.MAX_LENGTH:
        errors.append(f"Must be at most {PasswordLimits.MAX_LENGTH} characters.")

    if PasswordLimits.REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        errors.append("Must contain at least one uppercase letter.")

    if PasswordLimits.REQUIRE_DIGIT and not re.search(r"\d", password):
        errors.append("Must contain at least one digit.")

    if PasswordLimits.REQUIRE_SPECIAL and not re.search(
        r"[!@#$%^&*()\-_=+\[\]{}|;:'\",.<>?/]", password
    ):
        errors.append("Must contain at least one special character.")

    if errors:
        raise PasswordValidationError(
            "Password does not meet complexity requirements: " + " | ".join(errors)
        )

    return password


# ══════════════════════════════════════════════════════════════
#  Padlock Functions  –  Email
# ══════════════════════════════════════════════════════════════

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def validate_email(email: str) -> str:
    """
    Padlock ❰AUTH-02❱: basic structural email validation.

    Returns:
        Normalised (lowercased) email.
    Raises:
        ValidationError for malformed addresses.
    """
    normalised = email.strip().lower()
    if not _EMAIL_RE.match(normalised):
        raise ValidationError(f"'{email}' is not a valid email address.")
    return normalised

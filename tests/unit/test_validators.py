"""
tests/unit/test_validators.py
──────────────────────────────
Unit tests for app/core/validators.py (Padlock constraints).

Target: 70 % of the total test suite (Testing Pyramid base layer).
These tests are pure Python – no DB, no HTTP, no I/O.
Each test exercises exactly ONE Padlock function.
"""

import pytest
from datetime import datetime, timedelta, timezone

from app.core.validators import (
    # Shift padlocks
    validate_shift_duration, validate_rest_period,
    validate_weekly_hours, requires_break, ShiftLimits,
    ShiftValidationError, RestPeriodViolationError,
    # Role padlocks
    validate_role, validate_role_elevation, has_permission, require_permission,
    UserRole, RoleLimits, RoleValidationError,
    # Auth padlocks
    validate_password, validate_email,
    PasswordValidationError, ValidationError,
)

NOW = datetime(2024, 6, 10, 8, 0, 0, tzinfo=timezone.utc)


# ══════════════════════════════════════════════════════════════
#  SHIFT-01: duration bounds
# ══════════════════════════════════════════════════════════════

class TestValidateShiftDuration:

    def test_valid_8h_shift_returns_hours(self):
        hours = validate_shift_duration(NOW, NOW + timedelta(hours=8))
        assert hours == pytest.approx(8.0)

    def test_minimum_boundary_exactly_1h(self):
        hours = validate_shift_duration(NOW, NOW + timedelta(hours=1))
        assert hours == pytest.approx(1.0)

    def test_maximum_boundary_exactly_12h(self):
        hours = validate_shift_duration(NOW, NOW + timedelta(hours=12))
        assert hours == pytest.approx(12.0)

    def test_below_minimum_raises(self):
        with pytest.raises(ShiftValidationError, match="below the minimum"):
            validate_shift_duration(NOW, NOW + timedelta(minutes=30))

    def test_above_maximum_raises(self):
        with pytest.raises(ShiftValidationError, match="exceeds the maximum"):
            validate_shift_duration(NOW, NOW + timedelta(hours=13))

    def test_end_before_start_raises(self):
        with pytest.raises(ShiftValidationError, match="strictly after start"):
            validate_shift_duration(NOW + timedelta(hours=2), NOW)

    def test_end_equal_start_raises(self):
        with pytest.raises(ShiftValidationError):
            validate_shift_duration(NOW, NOW)

    def test_just_below_max_is_valid(self):
        hours = validate_shift_duration(NOW, NOW + timedelta(hours=11, minutes=59))
        assert hours < ShiftLimits.MAX_HOURS

    def test_just_above_min_is_valid(self):
        hours = validate_shift_duration(NOW, NOW + timedelta(hours=1, minutes=1))
        assert hours > ShiftLimits.MIN_HOURS


# ══════════════════════════════════════════════════════════════
#  SHIFT-02: rest period
# ══════════════════════════════════════════════════════════════

class TestValidateRestPeriod:

    def test_sufficient_rest_passes(self):
        prev_end   = NOW
        next_start = NOW + timedelta(hours=12)
        validate_rest_period(prev_end, next_start)  # should not raise

    def test_exact_minimum_rest_passes(self):
        validate_rest_period(NOW, NOW + timedelta(hours=ShiftLimits.MIN_REST_HOURS))

    def test_insufficient_rest_raises(self):
        with pytest.raises(RestPeriodViolationError, match="minimum required"):
            validate_rest_period(NOW, NOW + timedelta(hours=10))

    def test_zero_rest_raises(self):
        with pytest.raises(RestPeriodViolationError):
            validate_rest_period(NOW, NOW)


# ══════════════════════════════════════════════════════════════
#  SHIFT-03: weekly hours
# ══════════════════════════════════════════════════════════════

class TestValidateWeeklyHours:

    def test_under_limit_passes(self):
        validate_weekly_hours(40.0)  # should not raise

    def test_at_limit_passes(self):
        validate_weekly_hours(ShiftLimits.MAX_WEEKLY_HOURS)

    def test_over_limit_raises(self):
        with pytest.raises(ShiftValidationError, match="legal maximum"):
            validate_weekly_hours(ShiftLimits.MAX_WEEKLY_HOURS + 0.1)

    def test_zero_passes(self):
        validate_weekly_hours(0.0)


# ══════════════════════════════════════════════════════════════
#  SHIFT-04: break advisory
# ══════════════════════════════════════════════════════════════

class TestRequiresBreak:

    def test_short_shift_no_break(self):
        assert requires_break(5.9) is False

    def test_threshold_shift_needs_break(self):
        assert requires_break(ShiftLimits.BREAK_THRESHOLD_HOURS) is True

    def test_long_shift_needs_break(self):
        assert requires_break(10.0) is True


# ══════════════════════════════════════════════════════════════
#  ROLE-01: role validation
# ══════════════════════════════════════════════════════════════

class TestValidateRole:

    @pytest.mark.parametrize("role_str", ["admin", "manager", "staff", "viewer"])
    def test_valid_roles_accepted(self, role_str):
        role = validate_role(role_str)
        assert role.value == role_str

    def test_case_insensitive(self):
        assert validate_role("ADMIN") == UserRole.ADMIN

    def test_invalid_role_raises(self):
        with pytest.raises(RoleValidationError, match="not a valid role"):
            validate_role("superuser")

    def test_empty_string_raises(self):
        with pytest.raises(RoleValidationError):
            validate_role("")


# ══════════════════════════════════════════════════════════════
#  ROLE-02: privilege escalation guard
# ══════════════════════════════════════════════════════════════

class TestValidateRoleElevation:

    def test_admin_can_assign_manager(self):
        validate_role_elevation(UserRole.ADMIN, UserRole.MANAGER)  # no raise

    def test_admin_can_assign_staff(self):
        validate_role_elevation(UserRole.ADMIN, UserRole.STAFF)

    def test_manager_cannot_assign_admin(self):
        with pytest.raises(RoleValidationError, match="privilege escalation"):
            validate_role_elevation(UserRole.MANAGER, UserRole.ADMIN)

    def test_staff_cannot_assign_peer_or_higher(self):
        with pytest.raises(RoleValidationError):
            validate_role_elevation(UserRole.STAFF, UserRole.STAFF)
        with pytest.raises(RoleValidationError):
            validate_role_elevation(UserRole.STAFF, UserRole.MANAGER)

    def test_cannot_assign_own_level(self):
        with pytest.raises(RoleValidationError):
            validate_role_elevation(UserRole.MANAGER, UserRole.MANAGER)


# ══════════════════════════════════════════════════════════════
#  ROLE-03/04: permission checks
# ══════════════════════════════════════════════════════════════

class TestPermissions:

    def test_admin_passes_any_minimum(self):
        for role in UserRole:
            assert has_permission(UserRole.ADMIN, role) is True

    def test_viewer_fails_all_except_viewer(self):
        assert has_permission(UserRole.VIEWER, UserRole.VIEWER) is True
        assert has_permission(UserRole.VIEWER, UserRole.STAFF)   is False

    def test_require_permission_raises_on_failure(self):
        with pytest.raises(RoleValidationError, match="requires at least"):
            require_permission(UserRole.STAFF, UserRole.ADMIN)

    def test_require_permission_passes_silently(self):
        require_permission(UserRole.ADMIN, UserRole.STAFF)  # no raise


# ══════════════════════════════════════════════════════════════
#  AUTH-01: password complexity
# ══════════════════════════════════════════════════════════════

class TestValidatePassword:

    def test_strong_password_passes(self):
        result = validate_password("Secure@12345")
        assert result == "Secure@12345"

    def test_too_short_raises(self):
        with pytest.raises(PasswordValidationError, match="at least"):
            validate_password("Ab@1")

    def test_no_uppercase_raises(self):
        with pytest.raises(PasswordValidationError, match="uppercase"):
            validate_password("secure@12345")

    def test_no_digit_raises(self):
        with pytest.raises(PasswordValidationError, match="digit"):
            validate_password("Secure@abcd")

    def test_no_special_char_raises(self):
        with pytest.raises(PasswordValidationError, match="special"):
            validate_password("Secure12345")

    def test_multiple_failures_reported_together(self):
        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password("bad")
        # Should contain multiple violations
        assert "|" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
#  AUTH-02: email validation
# ══════════════════════════════════════════════════════════════

class TestValidateEmail:

    def test_valid_email_normalised(self):
        assert validate_email("User@Example.COM") == "user@example.com"

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError, match="valid email"):
            validate_email("not-an-email")

    def test_missing_domain_raises(self):
        with pytest.raises(ValidationError):
            validate_email("user@")

    def test_missing_at_raises(self):
        with pytest.raises(ValidationError):
            validate_email("userexample.com")

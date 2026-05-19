"""
tests/unit/test_auth_dependencies.py
──────────────────────────────────────
Unit tests for app/dependencies.py — get_current_user() and require_role().

Testing Pyramid layer: UNIT (70 %).
  • No real database — db.get() is mocked via unittest.mock.MagicMock.
  • decode_access_token is patched at its import site in app.dependencies.
  • No HTTP server — functions are called directly.
  • Each test covers exactly one failure/success branch.

TDD contract: every assertion is tight enough to fail if the corresponding
implementation branch is removed or changed.
"""

# ── env vars MUST be set before any `from app.*` import ───────────────────────
# app.core.config calls pydantic-settings at import time and requires these.
import os

os.environ.setdefault("SECRET_KEY", "unit-test-secret-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("APP_ENV", "testing")
# ──────────────────────────────────────────────────────────────────────────────

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import JWTError

from app.dependencies import get_current_user, require_role
from app.models.user import User, UserRole

# ── Patch target ──────────────────────────────────────────────────────────────
# Must be the import site in app.dependencies, not the definition in
# app.core.security — patching the source after the name is already bound
# would have no effect on the running code.
_DECODE = "app.dependencies.decode_access_token"

# A sentinel token string — content is irrelevant because decode is mocked.
_TOKEN = "header.payload.signature"


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_user(**overrides) -> SimpleNamespace:
    """Return a lightweight namespace that quacks like a User ORM object.

    Defaults represent a healthy, active, non-deleted user with token_version=1.
    Pass keyword overrides to tailor for a specific test scenario.
    """
    defaults = dict(
        id=1,
        email="user@example.com",
        role=UserRole.STAFF,
        is_active=True,
        is_deleted=False,
        token_version=1,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# =============================================================================
#  get_current_user()
# =============================================================================

@pytest.mark.unit
class TestGetCurrentUser:
    """
    Direct unit tests for get_current_user(token, db).

    FastAPI dependency injection is bypassed: token and db are passed as plain
    arguments.  db.get() is replaced by a MagicMock so no database is touched.
    """

    # ── Case 1 ────────────────────────────────────────────────────────────────

    def test_valid_token_matching_version_returns_user(self):
        """Happy path: correct token, correct version → the ORM user is returned."""
        user = _make_user(id=42, token_version=3)
        mock_db = MagicMock()
        mock_db.get.return_value = user

        with patch(_DECODE, return_value={"sub": "42", "ver": 3}):
            result = get_current_user(token=_TOKEN, db=mock_db)

        assert result is user
        # Verify the repository was asked for the right primary key.
        mock_db.get.assert_called_once_with(User, 42)

    # ── Case 2 ────────────────────────────────────────────────────────────────

    def test_expired_token_raises_401(self):
        """JWTError from decode_access_token (e.g. expiry) must surface as HTTP 401."""
        mock_db = MagicMock()

        with patch(_DECODE, side_effect=JWTError("Signature has expired")):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=_TOKEN, db=mock_db)

        assert exc_info.value.status_code == 401
        # DB must never be queried when the token itself is invalid.
        mock_db.get.assert_not_called()

    # ── Case 3 ────────────────────────────────────────────────────────────────

    def test_missing_ver_claim_raises_401(self):
        """A JWT that lacks the 'ver' claim must be rejected with HTTP 401."""
        mock_db = MagicMock()

        with patch(_DECODE, return_value={"sub": "1"}):  # no "ver"
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=_TOKEN, db=mock_db)

        assert exc_info.value.status_code == 401
        mock_db.get.assert_not_called()

    # ── Case 4 ────────────────────────────────────────────────────────────────

    def test_missing_sub_claim_raises_401(self):
        """A JWT that lacks the 'sub' claim must be rejected with HTTP 401."""
        mock_db = MagicMock()

        with patch(_DECODE, return_value={"ver": 1}):  # no "sub"
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=_TOKEN, db=mock_db)

        assert exc_info.value.status_code == 401
        mock_db.get.assert_not_called()

    # ── Case 5 ────────────────────────────────────────────────────────────────

    def test_user_not_found_in_db_raises_401(self):
        """If db.get() returns None the request must be rejected with HTTP 401."""
        mock_db = MagicMock()
        mock_db.get.return_value = None  # user does not exist

        with patch(_DECODE, return_value={"sub": "99", "ver": 1}):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=_TOKEN, db=mock_db)

        assert exc_info.value.status_code == 401
        mock_db.get.assert_called_once_with(User, 99)

    # ── Case 6 ────────────────────────────────────────────────────────────────

    def test_deleted_user_raises_401(self):
        """Soft-deleted users (is_deleted=True) must be treated as non-existent → 401."""
        user = _make_user(id=7, token_version=1, is_deleted=True)
        mock_db = MagicMock()
        mock_db.get.return_value = user

        with patch(_DECODE, return_value={"sub": "7", "ver": 1}):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=_TOKEN, db=mock_db)

        assert exc_info.value.status_code == 401

    # ── Case 7 ────────────────────────────────────────────────────────────────

    def test_token_version_mismatch_raises_401_with_invalidated_in_detail(self):
        """HR-04: token_version in JWT != user.token_version → 401, 'invalidated' in detail.

        This guards against tokens that were valid before a password change.
        The detail message must contain the word 'invalidated' so callers can
        prompt the user to re-authenticate rather than showing a generic error.
        """
        # DB has version 2 (password was changed after the token was issued).
        user = _make_user(id=5, token_version=2, is_deleted=False)
        mock_db = MagicMock()
        mock_db.get.return_value = user

        # Token was issued with version 1 — now stale.
        with patch(_DECODE, return_value={"sub": "5", "ver": 1}):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=_TOKEN, db=mock_db)

        assert exc_info.value.status_code == 401
        assert "invalidated" in exc_info.value.detail.lower()


# =============================================================================
#  require_role()
# =============================================================================

@pytest.mark.unit
class TestRequireRole:
    """
    Unit tests for the require_role() dependency factory (AU-05).

    require_role() returns a fastapi.Depends() wrapper.  The inner check
    function is accessible via .dependency and accepts current_user directly,
    so no FastAPI request lifecycle is needed.
    """

    # ── Case 8 ────────────────────────────────────────────────────────────────

    def test_admin_user_passes_admin_only_endpoint(self):
        """ADMIN role satisfies a require_role(ADMIN) guard → user object returned."""
        user = _make_user(role=UserRole.ADMIN)
        checker = require_role(UserRole.ADMIN).dependency

        result = checker(current_user=user)

        assert result is user

    # ── Case 9 ────────────────────────────────────────────────────────────────

    def test_staff_user_blocked_from_admin_only_endpoint(self):
        """STAFF role does not satisfy require_role(ADMIN) → HTTP 403."""
        user = _make_user(role=UserRole.STAFF)
        checker = require_role(UserRole.ADMIN).dependency

        with pytest.raises(HTTPException) as exc_info:
            checker(current_user=user)

        assert exc_info.value.status_code == 403

    # ── Case 10 ───────────────────────────────────────────────────────────────

    def test_admin_user_passes_admin_or_staff_endpoint(self):
        """ADMIN role satisfies require_role(ADMIN, STAFF) → user object returned."""
        user = _make_user(role=UserRole.ADMIN)
        checker = require_role(UserRole.ADMIN, UserRole.STAFF).dependency

        result = checker(current_user=user)

        assert result is user

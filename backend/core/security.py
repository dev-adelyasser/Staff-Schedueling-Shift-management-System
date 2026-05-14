"""
app/core/security.py
────────────────────
Authentication primitives: password hashing and JWT lifecycle.

Architectural contract
──────────────────────
  This module is a PURE UTILITY layer — it has zero knowledge of:
    • HTTP (no Request / Response objects)
    • Database (no Session, no ORM imports)
    • Business rules (no role checks, no user lookups)

  It is deliberately thin.  Service-layer callers own the business
  decisions; this module only provides cryptographic operations.

Security choices
────────────────
  Hashing  : bcrypt via passlib (adaptive cost factor, salted)
  JWT algo : HS256 — symmetric, sufficient for a single-service system.
             Swap to RS256 (asymmetric) if a separate auth microservice
             is introduced in a later phase.
  Claims   : sub (subject = user_id), exp (expiry), iat (issued-at),
             jti (token ID — enables future token revocation).

Padlock cross-reference
───────────────────────
  AUTH-03 : token TTL comes from settings.access_token_expire_minutes
  AUTH-04 : max_login_attempts enforced in UserService, NOT here
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


# ─────────────────────────────────────────────────────────────────────────────
#  Password hashing
# ─────────────────────────────────────────────────────────────────────────────

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",          # auto-rehash on verify if cost factor increases
    bcrypt__rounds=12,          # OWASP recommended minimum as of 2024
)


def hash_password(plain_password: str) -> str:
    """
    Return a bcrypt hash of *plain_password*.
    The salt is embedded in the returned string — never stored separately.

    >>> hash_password("mysecret")   # returns a $2b$... string
    """
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Constant-time comparison of *plain_password* against *hashed_password*.
    Returns True if they match, False otherwise.

    Timing-safe: passlib's verify() never short-circuits on mismatch.
    """
    return _pwd_context.verify(plain_password, hashed_password)


def needs_rehash(hashed_password: str) -> bool:
    """
    Returns True if *hashed_password* was created with an outdated cost factor.
    Call this after a successful verify() and rehash transparently on login.
    """
    return _pwd_context.needs_update(hashed_password)


# ─────────────────────────────────────────────────────────────────────────────
#  JWT creation
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(
    subject: str | int | Any,
    *,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Encode and sign a JWT access token.

    Args:
        subject:      The token subject, typically a user ID (str or int).
        expires_delta: Override the default TTL from settings.
        extra_claims:  Optional dict merged into the payload (e.g. {"role": "admin"}).
                       Must not shadow reserved claims (sub, exp, iat, jti).

    Returns:
        A signed JWT string.

    Example:
        token = create_access_token(subject=user.id, extra_claims={"role": user.role})
    """
    now    = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.access_token_expire_minutes)
    )

    payload: dict[str, Any] = {
        "sub": str(subject),         # always a string per JWT spec
        "exp": expire,               # jose encodes datetime → numeric timestamp
        "iat": now,                  # issued-at (useful for audit logs)
        "jti": str(uuid.uuid4()),    # unique token ID (enables revocation lists)
        "typ": "access",             # distinguish from refresh tokens if added later
    }

    if extra_claims:
        # Safety guard: never allow caller to overwrite reserved claims
        _RESERVED = {"sub", "exp", "iat", "jti", "typ"}
        forbidden = _RESERVED & extra_claims.keys()
        if forbidden:
            raise ValueError(
                f"extra_claims must not shadow reserved JWT claims: {forbidden}"
            )
        payload.update(extra_claims)

    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: str | int | Any) -> str:
    """
    Encode a longer-lived refresh token (7 days).
    Scaffold for Phase 3 — refresh endpoint not yet implemented.
    """
    return create_access_token(
        subject=subject,
        expires_delta=timedelta(days=7),
        extra_claims={"typ": "refresh"},  # type: ignore[dict-item]  noqa: overwrite intentional here
    )


# ─────────────────────────────────────────────────────────────────────────────
#  JWT verification
# ─────────────────────────────────────────────────────────────────────────────

class TokenPayload:
    """
    Typed wrapper around a decoded JWT payload.

    Attributes:
        sub  : Subject — the user's ID as a string.
        exp  : Expiry datetime (UTC).
        iat  : Issued-at datetime (UTC).
        jti  : Unique token identifier.
        role : Optional role claim embedded by create_access_token.
    """

    __slots__ = ("sub", "exp", "iat", "jti", "role", "_raw")

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw  = raw
        self.sub   = raw["sub"]
        self.jti   = raw.get("jti", "")
        self.role  = raw.get("role")
        # jose decodes exp/iat as Python datetime objects when the claim is
        # a numeric timestamp — confirm and normalise to UTC.
        self.exp   = _ensure_utc(raw.get("exp"))
        self.iat   = _ensure_utc(raw.get("iat"))

    @property
    def user_id(self) -> int:
        """Convenience: parse sub as integer user ID."""
        return int(self.sub)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TokenPayload sub={self.sub!r} exp={self.exp}>"


def decode_access_token(token: str) -> TokenPayload:
    """
    Verify signature and expiry, then return a typed TokenPayload.

    Raises:
        jose.JWTError  : signature invalid, token expired, or malformed.

    Callers (typically a FastAPI security dependency) should catch JWTError
    and convert it to HTTP 401 Unauthorized.

    Example (FastAPI dependency):
        async def get_current_user(
            token: str = Depends(oauth2_scheme),
            db: Session = Depends(get_db),
        ) -> User:
            try:
                payload = decode_access_token(token)
            except JWTError:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
            user = user_repo.get_by_id(db, payload.user_id)
            if not user or not user.is_active:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inactive user")
            return user
    """
    raw = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        options={"verify_exp": True},   # always verify expiry
    )
    return TokenPayload(raw)


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_utc(value: datetime | int | float | None) -> datetime | None:
    """Normalise numeric UNIX timestamps returned by jose to UTC datetimes."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value

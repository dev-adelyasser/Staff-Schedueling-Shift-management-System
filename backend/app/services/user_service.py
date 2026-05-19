"""
app/services/user_service.py
─────────────────────────────
Business-logic layer for the User slice.

Layer contract:
  - This is the ONLY layer allowed to convert schema ↔ model.
  - Domain rules (HR-04 token invalidation, soft-delete, duplicate-email
    guard) live here — never in routers or repositories.
  - Repositories handle DB I/O only; this layer owns all decisions.
  - Raw ORM User objects must NOT leave this module unless the caller is
    authenticate_user (which returns User so the router can build the JWT).
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories import user_repository
from app.schemas.user import UserCreateSchema, UserResponseSchema, UserUpdateSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _404(user_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"User {user_id} not found",
    )


def _401_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_user(db: Session, data: UserCreateSchema) -> UserResponseSchema:
    """Register a new user (FR-02).

    Raises HTTP 409 if the email address is already in use.
    Passwords are hashed here; the repository never sees a plain-text password.
    token_version starts at 1 (not the model default of 0) so the first
    issued JWT carries a non-zero version, keeping HR-04 logic unambiguous.
    """
    if user_repository.get_by_email(db, data.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that email already exists",
        )

    user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        role=data.role,
        token_version=1,   # HR-04: start at 1 so ver=0 is always invalid
        is_deleted=False,
        # NOTE: first_name / last_name are non-nullable columns on the model
        # but are absent from UserCreateSchema. Set to "" until the model and
        # schema are aligned (tracked separately — schema-model gap).
        first_name="",
        last_name="",
    )
    created = user_repository.create(db, user)
    return UserResponseSchema.model_validate(created)


def get_user(db: Session, user_id: int) -> UserResponseSchema:
    """Return the profile for an active user.

    Raises HTTP 404 if the user does not exist or has been soft-deleted.
    Soft-deleted users are treated as non-existent to callers (AU-03).
    """
    user = user_repository.get_by_id(db, user_id)
    if user is None or user.is_deleted:
        raise _404(user_id)
    return UserResponseSchema.model_validate(user)


def update_user(
    db: Session,
    user_id: int,
    data: UserUpdateSchema,
) -> UserResponseSchema:
    """Apply a partial update to an existing user record.

    HR-04: if data.password is supplied the password is re-hashed AND
    token_version is incremented, immediately invalidating all JWTs that
    were issued before this call.

    Raises HTTP 404 if the user does not exist (deleted users included —
    a deleted user cannot be updated).
    """
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise _404(user_id)

    if data.email is not None:
        user.email = data.email.lower()

    if data.role is not None:
        user.role = data.role

    if data.password is not None:
        user.hashed_password = hash_password(data.password)
        user.token_version += 1  # HR-04: invalidate all previously issued JWTs

    updated = user_repository.update(db, user)
    return UserResponseSchema.model_validate(updated)


def delete_user(db: Session, user_id: int) -> None:
    """Soft-delete a user — the row is retained, is_deleted is set to True.

    Hard deletes are forbidden. repository.soft_delete() sets is_deleted
    and deleted_at; this service never calls db.delete().

    Raises HTTP 404 if no user with that id exists.
    """
    found = user_repository.soft_delete(db, user_id)
    if not found:
        raise _404(user_id)


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Verify credentials and return the raw ORM User on success.

    Returns the ORM User object (not a schema) so the caller (router) can
    read user.id and user.token_version to build the JWT via
    security.create_access_token().

    Raises HTTP 401 with a deliberately vague message on ANY failure so
    callers cannot distinguish between unknown email and wrong password
    (timing-safe enumeration guard).

    ── TODO (Person 1) ──────────────────────────────────────────────────────
    Fill in the three steps below:

      1. Fetch the user:
             user = user_repository.get_by_email(db, email)

      2. Reject if not found, soft-deleted, or inactive:
             if user is None or user.is_deleted or not user.is_active:
                 raise _401_credentials()

      3. Verify the password (timing-safe via passlib):
             if not verify_password(password, user.hashed_password):
                 raise _401_credentials()

      4. Return the user so the router can issue a JWT:
             return user
    ─────────────────────────────────────────────────────────────────────────
    """
    raise _401_credentials()

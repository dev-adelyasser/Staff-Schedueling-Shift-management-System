"""
app/services/user_service.py
─────────────────────────────
Business logic layer for User operations.

Service layer rules:
  • Calls Padlock validators BEFORE any DB write.
  • Calls repositories for data access; never raw ORM.
  • Returns schema objects (or ORM objects mapped in the router layer).
  • Raises domain exceptions that routers translate into HTTP responses.
"""

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, create_access_token
from app.core.validators import (
    UserRole, validate_role_elevation, require_permission,
    RoleValidationError,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserAlreadyExistsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UserService:

    def __init__(self, db: Session) -> None:
        self._repo = UserRepository(db)

    # ── Registration ──────────────────────────────────────────

    def register(self, payload: UserCreate) -> User:
        if self._repo.exists_by_email(payload.email):
            raise UserAlreadyExistsError(
                f"A user with email '{payload.email}' already exists."
            )
        user = self._repo.create(
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            role=payload.role,
        )
        return user

    # ── Auth ──────────────────────────────────────────────────

    def authenticate(self, email: str, password: str) -> str:
        """Returns JWT access token on success."""
        user = self._repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password.")
        if not user.is_active:
            raise InvalidCredentialsError("Account is inactive.")
        return create_access_token(subject=user.id)

    # ── Read ──────────────────────────────────────────────────

    def get_by_id(self, user_id: int) -> User:
        user = self._repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found.")
        return user

    def list_users(self, *, skip: int = 0, limit: int = 100) -> list[User]:
        return self._repo.list_all(skip=skip, limit=limit)

    # ── Update ────────────────────────────────────────────────

    def update_user(
        self, user_id: int, payload: UserUpdate, *, actor_role: UserRole
    ) -> User:
        user = self.get_by_id(user_id)

        # Padlock ROLE-02: prevent privilege escalation
        if payload.role and payload.role != user.role:
            validate_role_elevation(actor_role, payload.role)

        updates: dict = payload.model_dump(exclude_none=True)
        if "password" in updates:
            updates["hashed_password"] = hash_password(updates.pop("password"))

        return self._repo.update(user, **updates)

    # ── Deactivate ────────────────────────────────────────────

    def deactivate(self, user_id: int, *, actor_role: UserRole) -> User:
        require_permission(actor_role, UserRole.MANAGER)
        user = self.get_by_id(user_id)
        return self._repo.update(user, is_active=False)

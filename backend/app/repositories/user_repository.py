"""
app/repositories/user_repository.py
────────────────────────────────────
Data-access layer for the User entity.

Repository pattern: ALL raw SQL / ORM queries are isolated here.
Services call repository methods; they never build queries themselves.
This enforces a clean separation that makes unit-testing trivial
(mock the repo, test the service logic in isolation).
"""

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.user import User
from app.core.validators import UserRole


class UserRepository:

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Read ──────────────────────────────────────────────────

    def get_by_id(self, user_id: int) -> User | None:
        return self._db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        return self._db.scalars(stmt).first()

    def list_all(self, *, skip: int = 0, limit: int = 100) -> list[User]:
        stmt = select(User).offset(skip).limit(limit).order_by(User.id)
        return list(self._db.scalars(stmt).all())

    def list_by_role(self, role: UserRole) -> list[User]:
        stmt = select(User).where(User.role == role).order_by(User.id)
        return list(self._db.scalars(stmt).all())

    # ── Write ─────────────────────────────────────────────────

    def create(self, *, email: str, full_name: str,
               hashed_password: str, role: UserRole) -> User:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=role,
        )
        self._db.add(user)
        self._db.flush()   # assign ID without committing
        return user

    def update(self, user: User, **kwargs) -> User:
        for key, val in kwargs.items():
            if val is not None and hasattr(user, key):
                setattr(user, key, val)
        self._db.flush()
        return user

    def delete(self, user: User) -> None:
        self._db.delete(user)
        self._db.flush()

    def exists_by_email(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == email.lower())
        return self._db.scalars(stmt).first() is not None

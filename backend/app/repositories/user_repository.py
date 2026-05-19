"""
app/repositories/user_repository.py
─────────────────────────────────────
Data-access layer for the User entity.

Constraints:
  - DB queries only — no domain logic, no password hashing, no JWT.
  - SQLAlchemy 2.0 style exclusively: db.get() for PK lookups,
    db.execute(select(...)) for filtered queries. Session.query() is banned.
  - flush() is used instead of commit() so the caller (service layer)
    controls the transaction boundary.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_by_id(db: Session, user_id: int) -> User | None:
    """Return the User row for the given primary key, or None."""
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    """Return the User row whose email matches (case-insensitive), or None."""
    stmt = select(User).where(User.email == email.lower())
    return db.execute(stmt).scalars().first()


def create(db: Session, user: User) -> User:
    """Persist a fully-populated User object supplied by the caller.

    The caller (service layer) is responsible for setting every field
    — including hashed_password and role — before passing the object in.
    flush() assigns the DB-generated PK without ending the transaction.
    """
    db.add(user)
    db.flush()
    return user


def update(db: Session, user: User) -> User:
    """Flush field mutations already applied by the caller to the tracked User.

    The caller sets whichever attributes need changing on the SQLAlchemy-
    tracked object before calling this function; the repository only
    persists those changes within the current transaction.
    """
    db.flush()
    return user


def soft_delete(db: Session, user_id: int) -> bool:
    """Mark a user as deleted without removing the row (soft delete).

    Sets is_deleted=True and deleted_at to the current UTC timestamp.
    Returns True when the user was found and marked deleted,
    False when no user with that id exists.
    """
    user = db.get(User, user_id)
    if user is None:
        return False
    user.is_deleted = True
    user.deleted_at = datetime.now(timezone.utc)
    db.flush()
    return True

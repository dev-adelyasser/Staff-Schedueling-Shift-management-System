"""
app/models/user.py
──────────────────
User ORM model.

Information Hiding rule: this file must NEVER be imported by
any schema or router.  Only repositories and services may touch it.
"""

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.core.validators import UserRole


class User(Base):
    __tablename__ = "users"

    # ── Primary key ───────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ── Identity ──────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # ── Auth (hashed – never store plaintext) ─────────────────
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)

    # ── Role (RBAC) ───────────────────────────────────────────
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole"), nullable=False, default=UserRole.STAFF
    )

    # ── Flags ─────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Audit timestamps ──────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────
    shifts: Mapped[list["Shift"]] = relationship(  # noqa: F821
        "Shift", back_populates="assignee", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r} role={self.role}>"

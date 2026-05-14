"""
app/models/shift.py
───────────────────
Shift ORM model.  A shift represents a single scheduled work block
assigned to one staff member.
"""

from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.core.validators import ShiftStatus


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ── Who is working ────────────────────────────────────────
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignee: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="shifts"
    )

    # ── When ──────────────────────────────────────────────────
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime]   = mapped_column(DateTime(timezone=True), nullable=False)

    # ── Metadata ──────────────────────────────────────────────
    title: Mapped[str]          = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None]   = mapped_column(Text, nullable=True)
    status: Mapped[ShiftStatus] = mapped_column(
        Enum(ShiftStatus, name="shiftstatus"),
        nullable=False,
        default=ShiftStatus.DRAFT,
    )

    # ── Which schedule this shift belongs to (optional) ───────
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    schedule: Mapped["Schedule"] = relationship(  # noqa: F821
        "Schedule", back_populates="shifts"
    )

    # ── Audit ─────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Shift id={self.id} user_id={self.user_id} status={self.status}>"

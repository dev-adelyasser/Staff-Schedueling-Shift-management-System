"""
app/models/schedule.py
──────────────────────
Schedule ORM model.

A Schedule is a named weekly container that groups multiple Shifts.
Managers publish schedules; staff view theirs.
"""

from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ── Identity ──────────────────────────────────────────────
    name: Mapped[str]         = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Coverage window ───────────────────────────────────────
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    week_end:   Mapped[date] = mapped_column(Date, nullable=False)

    # ── Who created this schedule ─────────────────────────────
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # ── Audit ─────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Schedule id={self.id} name={self.name!r} week={self.week_start}>"

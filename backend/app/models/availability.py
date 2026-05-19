"""
app/models/availability.py
──────────────────────────
Staff availability windows — Slice 4.

day_of_week: 0 = Monday … 6 = Sunday (ISO weekday - 1).
A staff member may have at most one availability row per day_of_week
(enforced by the unique constraint).
"""

from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StaffAvailability(Base):
    __tablename__ = "staff_availability"
    __table_args__ = (
        UniqueConstraint("staff_id", "day_of_week", name="uq_availability_staff_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    staff_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0–6
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StaffAvailability staff={self.staff_id} day={self.day_of_week}>"

"""
app/models/staff_assignment.py
──────────────────────────────
Records which staff member is assigned to which shift.

The index on staff_id is the anchor for AU-04 overlap checks —
every query in has_overlapping_assignment() filters on this column.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StaffAssignment(Base):
    __tablename__ = "staff_assignments"
    __table_args__ = (
        UniqueConstraint("shift_id", "staff_id", name="uq_staff_assignment_shift_staff"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    shift_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    staff_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,          # AU-04: single indexed column for overlap queries
    )
    assigned_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    shift: Mapped["Shift"] = relationship("Shift", back_populates="assignments")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StaffAssignment shift={self.shift_id} staff={self.staff_id}>"

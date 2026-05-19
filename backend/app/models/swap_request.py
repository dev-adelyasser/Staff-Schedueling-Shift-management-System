"""
app/models/swap_request.py
──────────────────────────
Shift-swap workflow — AU-08.

State machine (enforced at service layer):
  PENDING → APPROVED
  PENDING → REJECTED
No other transitions are permitted.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SwapStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SwapRequest(Base):
    __tablename__ = "swap_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requester_shift_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_shift_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[SwapStatus] = mapped_column(
        SQLEnum(SwapStatus, name="swap_status", native_enum=True),
        nullable=False,
        default=SwapStatus.PENDING,
        server_default="PENDING",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    requester_shift: Mapped["Shift"] = relationship(  # noqa: F821
        "Shift", foreign_keys=[requester_shift_id]
    )
    target_shift: Mapped["Shift"] = relationship(  # noqa: F821
        "Shift", foreign_keys=[target_shift_id]
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SwapRequest id={self.id} status={self.status.value}>"

"""
app/models/audit_log.py
───────────────────────
Immutable audit trail — AU-07.

Rows are NEVER updated or deleted.  Written in the SAME transaction as every
INSERT / UPDATE / DELETE on shifts, staff_assignments, and swap_requests.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditActionType(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    actor_id: Mapped[int | None] = mapped_column(
        # nullable so system-generated events (e.g. cascade deletes) are recordable
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action_type: Mapped[AuditActionType] = mapped_column(
        SQLEnum(AuditActionType, name="audit_action_type", native_enum=True),
        nullable=False,
    )
    target_table: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AuditLog {self.action_type.value} on {self.target_table}"
            f" target={self.target_id} by={self.actor_id}>"
        )

"""
app/repositories/audit_log_repository.py
─────────────────────────────────────────
Write-only repository for audit_logs — AU-07.

Rows are never updated or deleted.  The caller is responsible for ensuring
this repository method is called within the same transaction as the write
being audited (call flush() — not commit() — before returning).
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionType, AuditLog


class AuditLogRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def record(
        self,
        *,
        actor_id: int | None,
        action_type: AuditActionType,
        target_table: str,
        target_id: uuid.UUID,
        before_state: dict[str, Any] | None,
        after_state: dict[str, Any] | None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_id=actor_id,
            action_type=action_type,
            target_table=target_table,
            target_id=target_id,
            before_state=before_state,
            after_state=after_state,
        )
        self._db.add(entry)
        self._db.flush()
        return entry

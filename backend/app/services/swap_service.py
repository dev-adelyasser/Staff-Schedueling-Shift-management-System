"""
app/services/swap_service.py
─────────────────────────────
Business logic for the Shift Swap workflow — Slice 6.

Invariants enforced here:
  AU-08 — three-state machine: PENDING → APPROVED | REJECTED only.
  HR-01 — SELECT FOR UPDATE on every approve/reject (via repo).
  HR-02 — audit log written in same transaction as every status change.
  HR-03 — rate limit: max 10 swap requests per user per hour.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionType
from app.models.swap_request import SwapStatus
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.swap_repository import SwapRepository
from app.schemas.swap import SwapRequestCreateSchema, SwapRequestResponseSchema

_RATE_LIMIT_MAX = 10
_RATE_LIMIT_WINDOW_HOURS = 1


class SwapNotFoundError(Exception):
    pass


class SwapRateLimitError(Exception):
    """Raised when a user exceeds HR-03 rate limit."""

    def __init__(self, retry_after_seconds: int = 3600) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded. Retry after {retry_after_seconds}s.")


class SwapConflictError(Exception):
    """AU-08: attempt to approve/reject a non-PENDING swap."""
    pass


class SwapService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = SwapRepository(db)
        self._audit = AuditLogRepository(db)

    # ── Create ─────────────────────────────────────────────────────────── #

    def create_swap(
        self,
        payload: SwapRequestCreateSchema,
        *,
        requester_id: int,
    ) -> SwapRequestResponseSchema:
        # HR-03: rate limit check
        recent = self._repo.count_recent_by_user(
            requester_id, window_hours=_RATE_LIMIT_WINDOW_HOURS
        )
        if recent >= _RATE_LIMIT_MAX:
            raise SwapRateLimitError()

        swap = self._repo.create(
            requester_id=requester_id,
            requester_shift_id=payload.requester_shift_id,
            target_shift_id=payload.target_shift_id,
            reason=payload.reason,
        )

        # HR-02 / AU-07: audit log in same transaction
        self._audit.record(
            actor_id=requester_id,
            action_type=AuditActionType.CREATE,
            target_table="swap_requests",
            target_id=swap.id,
            before_state=None,
            after_state=self._swap_snapshot(swap),
        )

        return SwapRequestResponseSchema.model_validate(swap)

    # ── Approve ────────────────────────────────────────────────────────── #

    def approve_swap(
        self,
        swap_id: uuid.UUID,
        *,
        actor_id: int,
    ) -> SwapRequestResponseSchema:
        # HR-01: SELECT FOR UPDATE — prevents concurrent double-approval (AU-08)
        swap = self._repo.get_for_update(swap_id)
        if swap is None:
            raise SwapNotFoundError(str(swap_id))

        if swap.status != SwapStatus.PENDING:
            raise SwapConflictError(
                f"Cannot approve swap in state {swap.status.value}"
            )

        before = self._swap_snapshot(swap)
        swap = self._repo.set_status(swap, SwapStatus.APPROVED, resolved_by=actor_id)

        # HR-02: audit log in same transaction
        self._audit.record(
            actor_id=actor_id,
            action_type=AuditActionType.UPDATE,
            target_table="swap_requests",
            target_id=swap.id,
            before_state=before,
            after_state=self._swap_snapshot(swap),
        )

        return SwapRequestResponseSchema.model_validate(swap)

    # ── Reject ─────────────────────────────────────────────────────────── #

    def reject_swap(
        self,
        swap_id: uuid.UUID,
        *,
        actor_id: int,
    ) -> SwapRequestResponseSchema:
        # HR-01: SELECT FOR UPDATE
        swap = self._repo.get_for_update(swap_id)
        if swap is None:
            raise SwapNotFoundError(str(swap_id))

        if swap.status != SwapStatus.PENDING:
            raise SwapConflictError(
                f"Cannot reject swap in state {swap.status.value}"
            )

        before = self._swap_snapshot(swap)
        swap = self._repo.set_status(swap, SwapStatus.REJECTED, resolved_by=actor_id)

        # HR-02
        self._audit.record(
            actor_id=actor_id,
            action_type=AuditActionType.UPDATE,
            target_table="swap_requests",
            target_id=swap.id,
            before_state=before,
            after_state=self._swap_snapshot(swap),
        )

        return SwapRequestResponseSchema.model_validate(swap)

    # ── Query ──────────────────────────────────────────────────────────── #

    def list_my_swaps(self, requester_id: int) -> list[SwapRequestResponseSchema]:
        swaps = self._repo.list_by_requester(requester_id)
        return [SwapRequestResponseSchema.model_validate(s) for s in swaps]

    # ── Private ────────────────────────────────────────────────────────── #

    @staticmethod
    def _swap_snapshot(swap) -> dict[str, Any]:
        return {
            "id": str(swap.id),
            "requester_id": swap.requester_id,
            "requester_shift_id": str(swap.requester_shift_id),
            "target_shift_id": str(swap.target_shift_id),
            "status": swap.status.value,
        }

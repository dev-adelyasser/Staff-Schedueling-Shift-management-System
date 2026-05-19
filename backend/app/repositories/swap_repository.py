"""
app/repositories/swap_repository.py
─────────────────────────────────────
DB queries for swap_requests.

approve() and reject() use SELECT FOR UPDATE (HR-01) to prevent concurrent
double-approval.  Both methods return the locked row for the service layer
to decide the outcome before committing.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.swap_request import SwapRequest, SwapStatus


class SwapRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Reads ──────────────────────────────────────────────────────────── #

    def get(self, swap_id: uuid.UUID) -> SwapRequest | None:
        return self._db.get(SwapRequest, swap_id)

    def get_for_update(self, swap_id: uuid.UUID) -> SwapRequest | None:
        """HR-01: SELECT FOR UPDATE — must be called inside an open transaction."""
        stmt = (
            select(SwapRequest)
            .where(SwapRequest.id == swap_id)
            .with_for_update()
        )
        return self._db.scalars(stmt).one_or_none()

    def count_recent_by_user(self, requester_id: int, *, window_hours: int = 1) -> int:
        """HR-03: count how many swaps this user submitted in the last window_hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        stmt = (
            select(func.count())
            .select_from(SwapRequest)
            .where(
                and_(
                    SwapRequest.requester_id == requester_id,
                    SwapRequest.created_at >= cutoff,
                )
            )
        )
        return self._db.scalar(stmt) or 0

    def list_by_requester(self, requester_id: int) -> list[SwapRequest]:
        stmt = select(SwapRequest).where(SwapRequest.requester_id == requester_id)
        return list(self._db.scalars(stmt))

    # ── Writes ─────────────────────────────────────────────────────────── #

    def create(
        self,
        *,
        requester_id: int,
        requester_shift_id: uuid.UUID,
        target_shift_id: uuid.UUID,
        reason: str | None,
    ) -> SwapRequest:
        swap = SwapRequest(
            requester_id=requester_id,
            requester_shift_id=requester_shift_id,
            target_shift_id=target_shift_id,
            reason=reason,
            status=SwapStatus.PENDING,
        )
        self._db.add(swap)
        self._db.flush()
        return swap

    def set_status(
        self,
        swap: SwapRequest,
        status: SwapStatus,
        *,
        resolved_by: int,
    ) -> SwapRequest:
        swap.status = status
        swap.resolved_at = datetime.now(timezone.utc)
        swap.resolved_by = resolved_by
        self._db.flush()
        return swap

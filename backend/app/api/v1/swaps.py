"""
app/api/v1/swaps.py
────────────────────
HTTP router for the Shift Swap workflow — Slice 6.

AU-08: three-state machine only (PENDING → APPROVED | REJECTED).
HR-01: SELECT FOR UPDATE enforced inside SwapService.
HR-03: 10 requests/user/hour; exceeded → HTTP 429 + Retry-After.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin, require_staff
from app.models.user import User
from app.schemas.swap import SwapRequestCreateSchema, SwapRequestResponseSchema
from app.services.swap_service import (
    SwapConflictError,
    SwapNotFoundError,
    SwapRateLimitError,
    SwapService,
)

router = APIRouter(prefix="/swaps", tags=["swaps"])


def _svc(db: Session = Depends(get_db)) -> SwapService:
    return SwapService(db)


# ── POST /swaps ──────────────────────────────────────────────────────────── #

@router.post(
    "/",
    response_model=SwapRequestResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Request a shift swap (STAFF only)",
)
def create_swap(
    payload: SwapRequestCreateSchema,
    current: Annotated[User, require_staff],
    svc: SwapService = Depends(_svc),
) -> SwapRequestResponseSchema:
    try:
        return svc.create_swap(payload, requester_id=current.id)
    except SwapRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: max 10 swap requests per hour.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Retry after 30 seconds.",
            headers={"Retry-After": "30"},
        )


# ── POST /swaps/{id}/approve ─────────────────────────────────────────────── #

@router.post(
    "/{swap_id}/approve",
    response_model=SwapRequestResponseSchema,
    summary="Approve a swap request (ADMIN only)",
)
def approve_swap(
    swap_id: uuid.UUID,
    current: Annotated[User, require_admin],
    svc: SwapService = Depends(_svc),
) -> SwapRequestResponseSchema:
    try:
        return svc.approve_swap(swap_id, actor_id=current.id)
    except SwapNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Swap not found")
    except SwapConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Retry after 30 seconds.",
            headers={"Retry-After": "30"},
        )


# ── POST /swaps/{id}/reject ──────────────────────────────────────────────── #

@router.post(
    "/{swap_id}/reject",
    response_model=SwapRequestResponseSchema,
    summary="Reject a swap request (ADMIN only)",
)
def reject_swap(
    swap_id: uuid.UUID,
    current: Annotated[User, require_admin],
    svc: SwapService = Depends(_svc),
) -> SwapRequestResponseSchema:
    try:
        return svc.reject_swap(swap_id, actor_id=current.id)
    except SwapNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Swap not found")
    except SwapConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Retry after 30 seconds.",
            headers={"Retry-After": "30"},
        )


# ── GET /swaps (own requests) ────────────────────────────────────────────── #

@router.get(
    "/",
    response_model=list[SwapRequestResponseSchema],
    summary="List my swap requests (STAFF)",
)
def list_my_swaps(
    current: Annotated[User, require_staff],
    svc: SwapService = Depends(_svc),
) -> list[SwapRequestResponseSchema]:
    return svc.list_my_swaps(current.id)

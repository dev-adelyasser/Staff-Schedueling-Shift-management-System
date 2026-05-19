"""
app/api/v1/availability.py
───────────────────────────
HTTP router for staff availability — Slice 4.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_any_role, require_staff
from app.models.user import User, UserRole
from app.schemas.availability import AvailabilityCreateSchema, AvailabilityResponseSchema
from app.services.availability_service import AvailabilityService

router = APIRouter(prefix="/availability", tags=["availability"])


def _svc(db: Session = Depends(get_db)) -> AvailabilityService:
    return AvailabilityService(db)


@router.put(
    "/",
    response_model=AvailabilityResponseSchema,
    summary="Set availability for the current staff member",
)
def set_availability(
    payload: AvailabilityCreateSchema,
    current: Annotated[User, require_staff],
    svc: AvailabilityService = Depends(_svc),
) -> AvailabilityResponseSchema:
    return svc.set_availability(current.id, payload)


@router.get(
    "/",
    response_model=list[AvailabilityResponseSchema],
    summary="Get availability for the current staff member",
)
def get_my_availability(
    current: Annotated[User, require_any_role],
    svc: AvailabilityService = Depends(_svc),
) -> list[AvailabilityResponseSchema]:
    return svc.get_availability(current.id)


@router.get(
    "/{staff_id}",
    response_model=list[AvailabilityResponseSchema],
    summary="Get availability for any staff member (ADMIN only)",
)
def get_staff_availability(
    staff_id: int,
    current: Annotated[User, require_any_role],
    svc: AvailabilityService = Depends(_svc),
) -> list[AvailabilityResponseSchema]:
    if current.role != UserRole.ADMIN and current.id != staff_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own availability.",
        )
    return svc.get_availability(staff_id)

"""
app/api/v1/attendance.py
─────────────────────────
HTTP router for Clock In / Clock Out — Slice 5 (UC-06).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_any_role, require_staff
from app.models.user import User
from app.schemas.attendance import AttendanceResponseSchema, ClockInSchema, ClockOutSchema
from app.services.attendance_service import (
    AttendanceAlreadyClockedInError,
    AttendanceNotClockedInError,
    AttendanceRecordNotFoundError,
    AttendanceService,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _svc(db: Session = Depends(get_db)) -> AttendanceService:
    return AttendanceService(db)


@router.post(
    "/clock-in",
    response_model=AttendanceResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Clock in (STAFF only)",
)
def clock_in(
    payload: ClockInSchema,
    current: Annotated[User, require_staff],
    svc: AttendanceService = Depends(_svc),
) -> AttendanceResponseSchema:
    try:
        return svc.clock_in(current.id, payload.shift_id)
    except AttendanceAlreadyClockedInError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/clock-out",
    response_model=AttendanceResponseSchema,
    summary="Clock out (STAFF only)",
)
def clock_out(
    payload: ClockOutSchema,
    current: Annotated[User, require_staff],
    svc: AttendanceService = Depends(_svc),
) -> AttendanceResponseSchema:
    try:
        return svc.clock_out(current.id, payload.record_id)
    except (AttendanceRecordNotFoundError, AttendanceNotClockedInError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/",
    response_model=list[AttendanceResponseSchema],
    summary="My attendance history (STAFF/ADMIN)",
)
def my_attendance(
    current: Annotated[User, require_any_role],
    svc: AttendanceService = Depends(_svc),
) -> list[AttendanceResponseSchema]:
    return svc.my_history(current.id)

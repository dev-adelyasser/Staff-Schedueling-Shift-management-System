"""
app/api/v1/shifts.py
─────────────────────
HTTP router for the Shift slice.

Rules:
  - Routers call service functions and return Pydantic schemas. Zero logic.
  - Auth guards come exclusively from app.dependencies (never reimplemented).
  - 503 on DB unavailability is handled by the global exception handler wired
    in main.py; individual handlers here cover domain errors only.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin, require_any_role
from app.models.user import User
from app.schemas.assignment import AssignmentCreateSchema, AssignmentResponseSchema
from app.schemas.shift import (
    BulkUploadResultSchema,
    ShiftCreateSchema,
    ShiftListResponseSchema,
    ShiftResponseSchema,
)
from app.services.shift_service import ShiftConflictError, ShiftNotFoundError, ShiftService

router = APIRouter(prefix="/shifts", tags=["shifts"])


def _svc(db: Session = Depends(get_db)) -> ShiftService:
    return ShiftService(db)


# ── POST /shifts ────────────────────────────────────────────────────────── #

@router.post(
    "/",
    response_model=ShiftResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shift (ADMIN only)",
)
def create_shift(
    payload: ShiftCreateSchema,
    background_tasks: BackgroundTasks,
    current: Annotated[User, require_admin],
    svc: ShiftService = Depends(_svc),
) -> ShiftResponseSchema:
    try:
        result = svc.create_shift(payload, actor_id=current.id)
        # BackgroundTask for notifications — failure here does NOT roll back (spec §19)
        background_tasks.add_task(_notify_shift_created, result)
        return result
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Retry after 30 seconds.",
            headers={"Retry-After": "30"},
        )


# ── GET /shifts ─────────────────────────────────────────────────────────── #

@router.get(
    "/",
    response_model=ShiftListResponseSchema,
    summary="List shifts (ADMIN + STAFF)",
)
def list_shifts(
    current: Annotated[User, require_any_role],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    department_id: int | None = Query(default=None),
    svc: ShiftService = Depends(_svc),
) -> ShiftListResponseSchema:
    try:
        return svc.list_shifts(skip=skip, limit=limit, department_id=department_id)
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Retry after 30 seconds.",
            headers={"Retry-After": "30"},
        )


# ── GET /shifts/{id} ─────────────────────────────────────────────────────── #

@router.get(
    "/{shift_id}",
    response_model=ShiftResponseSchema,
    summary="Get a single shift (ADMIN + STAFF)",
)
def get_shift(
    shift_id: uuid.UUID,
    current: Annotated[User, require_any_role],
    svc: ShiftService = Depends(_svc),
) -> ShiftResponseSchema:
    try:
        return svc.get_shift(shift_id)
    except ShiftNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Retry after 30 seconds.",
            headers={"Retry-After": "30"},
        )


# ── POST /shifts/{id}/assign ──────────────────────────────────────────────── #

@router.post(
    "/{shift_id}/assign",
    response_model=ShiftResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Assign staff to a shift (ADMIN only)",
)
def assign_shift(
    shift_id: uuid.UUID,
    payload: AssignmentCreateSchema,
    current: Annotated[User, require_admin],
    svc: ShiftService = Depends(_svc),
) -> ShiftResponseSchema:
    try:
        return svc.assign_staff(shift_id, payload.staff_id, actor_id=current.id)
    except ShiftNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    except ShiftConflictError as exc:
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


# ── POST /shifts/bulk-upload ──────────────────────────────────────────────── #

@router.post(
    "/bulk-upload",
    response_model=BulkUploadResultSchema,
    summary="Bulk-create shifts from a CSV file (ADMIN only)",
)
def bulk_upload_shifts(
    file: UploadFile,
    current: Annotated[User, require_admin],
    svc: ShiftService = Depends(_svc),
) -> BulkUploadResultSchema:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted.",
        )
    raw = file.file.read().decode("utf-8")
    try:
        result = svc.bulk_upload(raw, actor_id=current.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except OperationalError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Retry after 30 seconds.",
            headers={"Retry-After": "30"},
        )

    if not result.created and result.errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.errors,
        )

    # 207 Multi-Status when some rows succeeded and some failed
    if result.created and result.errors:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_207_MULTI_STATUS,
            content=result.model_dump(mode="json"),
        )

    return result


# ── Background task ────────────────────────────────────────────────────────── #

def _notify_shift_created(shift: ShiftResponseSchema) -> None:
    # TODO: dispatch push / email notification
    pass

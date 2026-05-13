"""
app/api/v1/endpoints/shifts.py
───────────────────────────────
Shift CRUD routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.shift import ShiftCreate, ShiftUpdate, ShiftResponse
from app.services.shift_service import ShiftService, ShiftNotFoundError
from app.core.validators import UserRole, ShiftValidationError

router = APIRouter(prefix="/shifts", tags=["Shifts"])


def _get_service(db: Session = Depends(get_db)) -> ShiftService:
    return ShiftService(db)


@router.post("/", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
def create_shift(payload: ShiftCreate, svc: ShiftService = Depends(_get_service)):
    try:
        return svc.create_shift(payload, actor_role=UserRole.MANAGER)
    except ShiftValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/", response_model=list[ShiftResponse])
def list_shifts(skip: int = 0, limit: int = 100, svc: ShiftService = Depends(_get_service)):
    return svc.list_shifts(skip=skip, limit=limit)


@router.get("/{shift_id}", response_model=ShiftResponse)
def get_shift(shift_id: int, svc: ShiftService = Depends(_get_service)):
    try:
        return svc.get_shift(shift_id)
    except ShiftNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{shift_id}", response_model=ShiftResponse)
def update_shift(
    shift_id: int, payload: ShiftUpdate, svc: ShiftService = Depends(_get_service)
):
    try:
        return svc.update_shift(shift_id, payload, actor_role=UserRole.MANAGER)
    except ShiftNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ShiftValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift(shift_id: int, svc: ShiftService = Depends(_get_service)):
    try:
        svc.delete_shift(shift_id, actor_role=UserRole.ADMIN)
    except ShiftNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))

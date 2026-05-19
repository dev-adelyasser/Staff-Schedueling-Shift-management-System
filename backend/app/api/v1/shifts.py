from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.shift import ShiftAssign, ShiftCreate, ShiftResponse, ShiftUpdate
from app.services.shift_service import ShiftService

router = APIRouter(prefix="/shifts", tags=["shifts"])


def _get_service(db: Session = Depends(get_db)) -> ShiftService:
    return ShiftService(db)


@router.get("/", response_model=list[ShiftResponse])
def list_shifts(
    skip: int = 0,
    limit: int = 100,
    current: User = Depends(get_current_user),  # auth guard — spec: STAFF or ADMIN
    svc: ShiftService = Depends(_get_service),
) -> list[ShiftResponse]:
    return svc.list_shifts(skip=skip, limit=limit)


@router.post("/", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
def create_shift(
    payload: ShiftCreate,
    current: User = Depends(get_current_user),
    svc: ShiftService = Depends(_get_service),
) -> ShiftResponse:
    if current.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager or Admin required")
    return svc.create_shift(payload, actor_id=current.id, actor_role=current.role)


@router.get("/{shift_id}", response_model=ShiftResponse)
def get_shift(
    shift_id: int,
    current: User = Depends(get_current_user),
    svc: ShiftService = Depends(_get_service),
) -> ShiftResponse:
    shift = svc.get_by_id(shift_id)
    if shift is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    return shift


@router.patch("/{shift_id}", response_model=ShiftResponse)
def update_shift(
    shift_id: int,
    payload: ShiftUpdate,
    current: User = Depends(get_current_user),
    svc: ShiftService = Depends(_get_service),
) -> ShiftResponse:
    if current.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager or Admin required")
    return svc.update_shift(shift_id, payload, actor_id=current.id)


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift(
    shift_id: int,
    current: User = Depends(get_current_user),
    svc: ShiftService = Depends(_get_service),
) -> None:
    if current.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager or Admin required")
    svc.delete_shift(shift_id, actor_role=current.role)


@router.post("/{shift_id}/assign", response_model=ShiftResponse)
def assign_shift(
    shift_id: int,
    payload: ShiftAssign,
    current: User = Depends(get_current_user),
    svc: ShiftService = Depends(_get_service),
) -> ShiftResponse:
    """Spec section 10: user assignment is a dedicated endpoint, not part of ShiftCreate."""
    if current.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager or Admin required")
    return svc.assign_shift(shift_id, payload.user_id, actor_id=current.id)

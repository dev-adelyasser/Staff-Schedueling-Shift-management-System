from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _get_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserCreate,
    svc: UserService = Depends(_get_service),
) -> UserResponse:
    """Register a new user. Returns UserResponse schema — never a raw ORM object."""
    return svc.register(payload)


@router.get("/", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    current: User = Depends(get_current_user), 
    svc: UserService = Depends(_get_service),
) -> list[UserResponse]:
    """List users — requires MANAGER or ADMIN role."""
    if current.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or Admin role required",
        )
    return svc.list_users(skip=skip, limit=limit)


@router.get("/me", response_model=UserResponse)
def get_me(current: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current: User = Depends(get_current_user),
    svc: UserService = Depends(_get_service),
) -> UserResponse:
    """Get a single user profile — requires being the owner or a MANAGER/ADMIN."""
    if current.id != user_id and current.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view this profile",
        )
        
    user = svc.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

"""
User registration, authentication, and profile endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.validators import RoleValidationError, UserRole
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
    UserService,
)

router = APIRouter()


def _svc(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    svc = UserService(db)
    try:
        return svc.register(payload)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/login", response_model=TokenResponse, summary="Obtain JWT access token")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    svc = UserService(db)
    try:
        token = svc.authenticate(email=str(payload.email), password=payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return TokenResponse(access_token=token)


@router.get("/", response_model=list[UserResponse], summary="List users")
def list_users(
    skip: int = 0,
    limit: int = 100,
    svc: UserService = Depends(_svc),
) -> list[User]:
    return svc.list_users(skip=skip, limit=limit)


@router.get("/me", response_model=UserResponse, summary="Current user profile")
def read_me(current: User = Depends(get_current_user)) -> User:
    return current


@router.get("/{user_id}", response_model=UserResponse, summary="Get user by id")
def get_user(user_id: int, svc: UserService = Depends(_svc)) -> User:
    try:
        return svc.get_by_id(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{user_id}", response_model=UserResponse, summary="Update user")
def update_user(
    user_id: int,
    payload: UserUpdate,
    current: User = Depends(get_current_user),
    svc: UserService = Depends(_svc),
) -> User:
    if current.id != user_id and current.role not in (UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="You may only update your own profile unless you are a manager.",
        )
    try:
        return svc.update_user(
            user_id, payload, actor_role=current.role
        )
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RoleValidationError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.patch(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate user (managers+)",
)
def deactivate_user(
    user_id: int,
    current: User = Depends(get_current_user),
    svc: UserService = Depends(_svc),
) -> User:
    try:
        return svc.deactivate(user_id, actor_role=current.role)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    except RoleValidationError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc))

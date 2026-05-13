"""
app/api/v1/endpoints/users.py
──────────────────────────────
User & Auth routes.  Routes only:
  • Parse/validate request schemas
  • Call the service layer
  • Return response schemas
  
They never touch ORM models or raw SQL.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, TokenResponse, LoginRequest,
)
from app.services.user_service import (
    UserService, UserAlreadyExistsError, UserNotFoundError,
    InvalidCredentialsError,
)
from app.core.validators import UserRole

router = APIRouter(prefix="/users", tags=["Users"])


def _get_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


# ── Auth ──────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, svc: UserService = Depends(_get_service)):
    try:
        token = svc.authenticate(payload.email, payload.password)
        return TokenResponse(access_token=token)
    except InvalidCredentialsError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc))


# ── CRUD ──────────────────────────────────────────────────────

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, svc: UserService = Depends(_get_service)):
    try:
        user = svc.register(payload)
        return user
    except UserAlreadyExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("/", response_model=list[UserResponse])
def list_users(
    skip: int = 0,
    limit: int = 100,
    svc: UserService = Depends(_get_service),
):
    return svc.list_users(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, svc: UserService = Depends(_get_service)):
    try:
        return svc.get_by_id(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    svc: UserService = Depends(_get_service),
):
    try:
        # TODO: extract actor_role from JWT in a real auth flow
        return svc.update_user(user_id, payload, actor_role=UserRole.ADMIN)
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))

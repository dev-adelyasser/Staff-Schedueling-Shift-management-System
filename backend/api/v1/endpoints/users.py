"""
app/api/v1/endpoints/users.py
──────────────────────────────
User resource and authentication endpoints.

Information Hiding enforcement
───────────────────────────────
  ✅ Imports only from: schemas/, services/, core/
  ❌ Never imports from: models/, repositories/, database.py directly

Route handler contract
──────────────────────
  Each handler ONLY:
    1. Parses the incoming schema (FastAPI does this automatically).
    2. Calls one service method.
    3. Maps the result to a response schema.
    4. Translates domain exceptions to HTTP responses.

  No SQL, no ORM, no business logic lives here.

Endpoints
──────────
  POST   /users/login        → authenticate and return JWT
  POST   /users/             → register new user
  GET    /users/             → list users (paginated)
  GET    /users/{user_id}    → get single user
  PATCH  /users/{user_id}    → partial update
  DELETE /users/{user_id}    → deactivate (soft delete)

TODO (Phase 3): Replace hardcoded actor_role=UserRole.ADMIN with a real
      `get_current_user` dependency that extracts the role from the JWT.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.validators import UserRole
from app.database import get_db
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

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={
        401: {"description": "Authentication failed"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "User not found"},
        409: {"description": "Email already registered"},
        422: {"description": "Validation error"},
    },
)


# ─────────────────────────────────────────────────────────────────────────────
#  Service factory dependency
# ─────────────────────────────────────────────────────────────────────────────

def _get_service(db: Session = Depends(get_db)) -> UserService:
    """
    Construct UserService with the request-scoped DB session.
    Keeps route handler signatures clean.
    """
    return UserService(db)


# ─────────────────────────────────────────────────────────────────────────────
#  Auth endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive a JWT access token",
)
def login(
    payload: LoginRequest,
    svc: UserService = Depends(_get_service),
) -> TokenResponse:
    """
    Exchange valid credentials for a JWT access token.

    - Verifies email + bcrypt password.
    - Returns 401 for both wrong email and wrong password (no oracle).
    - Returns 401 for inactive accounts (same message, no info leak).
    """
    try:
        token = svc.authenticate(payload.email, payload.password)
        return TokenResponse(access_token=token)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─────────────────────────────────────────────────────────────────────────────
#  CRUD endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def create_user(
    payload: UserCreate,
    svc: UserService = Depends(_get_service),
) -> UserResponse:
    """
    Create a new user account.

    - Password is hashed before storage (never stored in plain text).
    - Email is normalised to lowercase.
    - Returns 409 if the email is already registered.
    """
    try:
        user = svc.register(payload)
        return user  # type: ignore[return-value]
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get(
    "/",
    response_model=list[UserResponse],
    summary="List all users (paginated)",
)
def list_users(
    skip: int  = Query(default=0,   ge=0,   description="Records to skip"),
    limit: int = Query(default=20,  ge=1, le=100, description="Max records to return"),
    svc: UserService = Depends(_get_service),
) -> list[UserResponse]:
    """
    Return a paginated list of users.
    `limit` is capped at 100 by the query parameter constraint.
    """
    return svc.list_users(skip=skip, limit=limit)  # type: ignore[return-value]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get a single user by ID",
)
def get_user(
    user_id: int,
    svc: UserService = Depends(_get_service),
) -> UserResponse:
    try:
        return svc.get_by_id(user_id)  # type: ignore[return-value]
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Partially update a user",
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    svc: UserService = Depends(_get_service),
) -> UserResponse:
    """
    PATCH semantics: only fields present in the payload are updated.
    Fields absent from the payload retain their current values.

    TODO (Phase 3): Replace actor_role=UserRole.ADMIN with JWT-derived role.
    """
    try:
        return svc.update_user(user_id, payload, actor_role=UserRole.ADMIN)  # type: ignore[return-value]
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a user (soft delete)",
)
def deactivate_user(
    user_id: int,
    svc: UserService = Depends(_get_service),
) -> None:
    """
    Soft-delete: sets is_active=False rather than removing the record.
    Historical shift data is preserved.

    TODO (Phase 3): Replace actor_role=UserRole.MANAGER with JWT-derived role.
    """
    try:
        svc.deactivate(user_id, actor_role=UserRole.MANAGER)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

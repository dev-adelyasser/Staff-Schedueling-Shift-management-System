from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.post("/token", response_model=TokenResponse, summary="FR-03: Login")
def login(
    payload: LoginRequest,
    svc: UserService = Depends(_get_service),
) -> TokenResponse:
    """
    Spec section 9 / FR-03 — Login endpoint.
    Acceptance tests hit POST /api/v1/auth/token.
    """
    token = svc.authenticate(payload.email, payload.password)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

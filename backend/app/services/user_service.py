from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate, UserResponse


class UserAlreadyExistsError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class UserService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = UserRepository(db)

    def register(self, payload: UserCreate) -> UserResponse:
        if self._repo.get_by_email(payload.email) is not None:
            raise UserAlreadyExistsError(payload.email)

        user = self._repo.create(payload)
        return UserResponse.model_validate(user)

    def authenticate(self, email: str, password: str) -> TokenResponse | None:
        user = self._repo.get_by_email(email)
        if user is None or user.is_deleted:
            return None
        if not verify_password(password, user.hashed_password):
            return None

        token = create_access_token(
            subject=user.id,
            token_version=user.token_version,  # HR-04
        )
        return TokenResponse(access_token=token)

    def get_by_id(self, user_id: int) -> UserResponse | None:
        user = self._repo.get(user_id)
        if user is None or user.is_deleted:
            return None
        return UserResponse.model_validate(user)

    def list_users(self, *, skip: int = 0, limit: int = 100) -> list[UserResponse]:
        users = self._repo.list(skip=skip, limit=limit)
        return [UserResponse.model_validate(u) for u in users]

    def change_password(self, user_id: int, new_password: str) -> None:
        """HR-04: increment token_version so all existing JWTs are invalidated."""
        user = self._repo.get(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

        user.hashed_password = hash_password(new_password)
        user.token_version += 1  # invalidates all previously issued tokens
        user.updated_at = datetime.now(timezone.utc)
        self._db.flush()

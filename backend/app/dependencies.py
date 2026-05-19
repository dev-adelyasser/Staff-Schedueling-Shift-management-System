from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        token_ver: int | None = payload.get("ver")
        if user_id is None or token_ver is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    # NOTE: int(user_id) assumes users.id is an INTEGER primary key.
    # If you switch to UUID, change this to: uuid.UUID(user_id)
    # and add: import uuid  at the top of this file.
    user: User | None = db.get(User, int(user_id))

    if user is None or user.is_deleted:
        raise credentials_exc

    # HR-04: reject tokens issued before the last password change
    if user.token_version != token_ver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ---------------------------------------------------------------------------
# require_role — AU-05: RBAC dependency factory
# ---------------------------------------------------------------------------

def require_role(*allowed_roles: UserRole):
    """
    Dependency factory that enforces role-based access control (AU-05).

    Guarantees:
      - Calls get_current_user first, so HR-04 and AU-03 are always enforced.
      - Role mismatch → HTTP 403 within 50 ms (FastAPI resolves Depends()
        synchronously in the request thread).

    Single-role usage (admin-only endpoint, FR-06):
        @router.post("/shifts", dependencies=[Depends(require_role(UserRole.ADMIN))])

    Multi-role usage (staff or admin can list shifts):
        @router.get("/shifts", dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.STAFF))])

    When you also need the user object inside the handler:
        def create_shift(
            payload: ShiftCreateSchema,
            current_user: User = require_role(UserRole.ADMIN),
            db: Session = Depends(get_db),
        ): ...
    """
    allowed: frozenset[UserRole] = frozenset(allowed_roles)

    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. Required role(s): "
                    f"{', '.join(r.value for r in sorted(allowed, key=lambda r: r.value))}."
                ),
            )
        return current_user

    # Return a Depends() directly so callers can use it in two ways:
    #   as a keyword default:      current_user: User = require_role(UserRole.ADMIN)
    #   or in dependencies=[...]:  dependencies=[Depends(require_role(UserRole.ADMIN))]
    return Depends(_check)


# ---------------------------------------------------------------------------
# Convenience aliases — import these in your routers to keep signatures terse.
# ---------------------------------------------------------------------------

# Any authenticated user, role not checked:
#   current_user: User = Depends(get_current_user)

# Admin-only (FR-06, AU-05):
#   current_user: User = require_admin
require_admin = require_role(UserRole.ADMIN)

# Staff-only:
#   current_user: User = require_staff
require_staff = require_role(UserRole.STAFF)

# Staff or Admin (e.g. GET /shifts):
#   current_user: User = require_any_role
require_any_role = require_role(UserRole.ADMIN, UserRole.STAFF)


from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Inbound credentials for POST /auth/token."""

    email: EmailStr
    password: str


class TokenSchema(BaseModel):
    """Outbound JWT envelope returned on successful login."""

    access_token: str
    token_type: str = "bearer"


class TokenDataSchema(BaseModel):
    """Validated claims extracted from a decoded JWT payload."""

    sub: str   # str(user_id)
    ver: int   # token_version — HR-04 stale-token guard

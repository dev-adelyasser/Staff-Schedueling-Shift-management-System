from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.shifts import router as shifts_router
from app.api.v1.endpoints.users import router as users_router

api_router = APIRouter()

api_router.include_router(auth_router)    # POST /api/v1/auth/token
api_router.include_router(users_router)   # /api/v1/users/...
api_router.include_router(shifts_router)  # /api/v1/shifts/...

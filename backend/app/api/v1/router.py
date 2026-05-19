from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.shifts import router as shifts_router
from app.api.v1.swaps import router as swaps_router
from app.api.v1.availability import router as availability_router
from app.api.v1.attendance import router as attendance_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(shifts_router)
api_router.include_router(swaps_router)
api_router.include_router(availability_router)
api_router.include_router(attendance_router)

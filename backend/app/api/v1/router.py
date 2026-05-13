"""
app/api/v1/router.py
─────────────────────
Aggregates all v1 endpoint routers.
main.py mounts this as /api/v1.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.users  import router as users_router
from app.api.v1.endpoints.shifts import router as shifts_router

api_v1_router = APIRouter()

api_v1_router.include_router(users_router)
api_v1_router.include_router(shifts_router)

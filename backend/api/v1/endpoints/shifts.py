"""
backend/app/api/v1/endpoints/shifts.py
───────────────────────────────────────
Shift endpoint stubs — Phase 3 skeleton.
Full CRUD logic and DB wiring arrive in Phase 4.
"""

from fastapi import APIRouter

router = APIRouter()


# Stub — returns empty list until Phase 4 wires the repository layer.
@router.get("/", summary="List shifts (stub)")
async def list_shifts() -> list:
    return []

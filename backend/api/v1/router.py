"""
app/api/v1/router.py
────────────────────
Version-1 API router — the single aggregation point for all v1 endpoints.

Vertical Slicing mount map
──────────────────────────
  Slice        Prefix            Module
  ──────────── ───────────────── ────────────────────────────────────────
  Auth/Users   /api/v1/users     app.api.v1.endpoints.users
  Shifts       /api/v1/shifts    app.api.v1.endpoints.shifts
  Schedules    /api/v1/schedules app.api.v1.endpoints.schedules  (Phase 3)
  ──────────── ───────────────── ────────────────────────────────────────

Information Hiding
──────────────────
  main.py calls:  app.include_router(api_v1_router, prefix="/api/v1")
  This file only performs include_router() calls — zero business logic.
  Adding a new vertical slice means adding ONE line here; no other file
  outside the slice needs to change.

Adding a new slice (checklist for Phase 3 / Phase 4)
──────────────────────────────────────────────────────
  1. Create  app/api/v1/endpoints/<slice>.py  with an APIRouter.
  2. Import  the router below.
  3. Add     api_v1_router.include_router(<slice>_router)
  4. Done — main.py does NOT need to change.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints.users  import router as users_router
from app.api.v1.endpoints.shifts import router as shifts_router

# ── Phase 3 placeholder — uncomment when slice is implemented ─────────────────
# from app.api.v1.endpoints.schedules import router as schedules_router

# ─────────────────────────────────────────────────────────────────────────────
#  Root v1 router
# ─────────────────────────────────────────────────────────────────────────────

api_v1_router = APIRouter()

# ── Registered slices ─────────────────────────────────────────────────────────
api_v1_router.include_router(users_router)
api_v1_router.include_router(shifts_router)

# ── Phase 3 — uncomment when ready ───────────────────────────────────────────
# api_v1_router.include_router(schedules_router)

"""
backend/app/api/v1/router.py
────────────────────────────
Aggregates all v1 endpoint routers into a single `api_v1_router`.

Information Hiding
──────────────────
`main.py` imports only `api_v1_router`.  It never sees individual endpoint
modules, so adding or removing routes never requires touching main.py.

Export name: `api_v1_router`
  — must match the import in app/main.py:
    `from app.api.v1.router import api_v1_router`

Phase 3 state: routers are registered; endpoint implementations are stubs.
Full DB-backed logic arrives in Phase 4.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import shifts, users

api_v1_router = APIRouter()

# Each include_router call maps a domain module to its URL prefix and
# groups it under an OpenAPI tag.  Adding a new domain (e.g. schedules)
# is a one-line change here — main.py never needs touching.
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])
api_v1_router.include_router(shifts.router, prefix="/shifts", tags=["Shifts"])

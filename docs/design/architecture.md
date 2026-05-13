# Staff Scheduling System – Architecture Decision Record

## Pattern: Vertical Slicing

Each feature slice (User, Shift, Schedule) owns its full stack:

```
schemas/ ← API contract (Pydantic)  [Information Hiding boundary]
   ↕
services/ ← Business logic + Padlock calls
   ↕
repositories/ ← Data access (SQLAlchemy ORM only)
   ↕
models/ ← Database entities (never leaked to API layer)
```

## Information Hiding

| Layer | May import from | NEVER imports from |
|---|---|---|
| `api/` routes | `schemas/`, `services/` | `models/`, `repositories/` |
| `services/` | `repositories/`, `core/`, `schemas/` | `api/` |
| `repositories/` | `models/` | `schemas/`, `services/`, `api/` |
| `schemas/` | `core/validators` | `models/`, `repositories/` |

## Edge Case Cage (Padlocks)

All boundary checks live in `app/core/validators.py`.  
No validator logic appears in routes or schemas.

| Padlock ID | Constraint | Layer enforced |
|---|---|---|
| SHIFT-01 | 1h ≤ shift ≤ 12h | `ShiftService.create_shift` |
| SHIFT-02 | ≥ 11h rest between shifts | `ShiftService.create_shift` |
| SHIFT-03 | ≤ 48h / week | `ShiftService.create_shift` |
| SHIFT-04 | Break if ≥ 6h (advisory) | `ShiftService` |
| ROLE-01  | Role must be valid enum | `UserSchema` + `UserService` |
| ROLE-02  | No privilege escalation | `UserService.update_user` |
| AUTH-01  | Password complexity | `UserSchema` |
| AUTH-02  | Email format | `UserSchema` |

## Testing Pyramid

```
        /\
       /E2E\        10% – Playwright + HTTP smoke tests
      /──────\
     /  Integ  \    20% – Real SQLite DB, real repos, TestClient
    /────────────\
   /    Unit      \  70% – Pure validator + service tests (no I/O)
  /────────────────\
```

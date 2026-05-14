# Staff Scheduling & Shift Management System

A modular FastAPI backend built with **Vertical Slicing**, **Information Hiding**, and a **Testing Pyramid** enforcement pipeline.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Running the API](#running-the-api)
- [Testing](#testing)
- [CI/CD Pipeline](#cicd-pipeline)
- [API Reference](#api-reference)
- [Design Constraints](#design-constraints)

---

## Overview

This system manages staff shifts and schedules with enforced business constraints (Padlock rules) at the service layer. It is built in phases:

| Phase | Goal | Status |
|---|---|---|
| 1 | Project scaffold & directory layout | ✅ Done |
| 2 | Settings, config, security foundations | ✅ Done |
| 3 | Hello World API + CI/CD pipeline | ✅ Done |
| 4 | Full DB integration, CRUD endpoints | 🔜 Next |

---

## Architecture

```
Request
  │
  ▼
FastAPI (main.py)
  │  mounts
  ▼
API Router (api/v1/router.py)
  │  delegates to
  ▼
Endpoints (api/v1/endpoints/)
  │  calls
  ▼
Services (services/)          ← Padlock business rules live here
  │  calls
  ▼
Repositories (repositories/)  ← All SQL queries isolated here
  │  uses
  ▼
Models (models/)              ← Never leaked to routes
  │
  ▼
Database (PostgreSQL via SQLAlchemy 2.x)
```

**Key principles:**

- `schemas/` define the public API contract — what callers see
- `models/` are internal — never returned directly from a route
- `services/` enforce the Padlock constraints (shift duration, weekly hours, rest periods)
- `repositories/` isolate every SQL query — services never write raw SQL
- `config.py` is the only file that reads environment variables — nothing else calls `os.environ`

---

## Project Structure

```
.
├── .github/
│   └── workflows/
│       └── ci.yml              # CI/CD pipeline (lint + test + coverage)
├── backend/
│   └── app/
│       ├── main.py             # App factory, middleware, health probes
│       ├── database.py         # Engine, Base, get_db dependency
│       ├── api/
│       │   └── v1/
│       │       ├── router.py           # Aggregates all v1 routers
│       │       └── endpoints/
│       │           ├── users.py
│       │           └── shifts.py
│       ├── core/
│       │   ├── config.py       # All env vars — single source of truth
│       │   ├── security.py     # JWT encoding/decoding, password hashing
│       │   └── validators.py   # Shared Pydantic validators
│       ├── models/             # SQLAlchemy ORM models (internal)
│       ├── schemas/            # Pydantic request/response schemas (public)
│       ├── services/           # Business logic + Padlock rules
│       └── repositories/       # SQL queries
├── tests/
│   ├── conftest.py             # Fixtures, test DB, dependency overrides
│   ├── unit/                   # 70% — no DB, no network
│   ├── integration/            # 20% — SQLite in-memory DB
│   └── e2e/                    # 10% — Playwright (Phase 4)
├── docs/
│   └── design/
│       └── architecture.md
├── docker-compose.yml
├── pytest.ini
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- Python 3.11
- Docker & Docker Compose (for the full stack with PostgreSQL)
- `pip` or a virtual environment manager

### Local setup (without Docker)

```bash
# 1. Clone the repo
git clone https://github.com/your-org/staff-scheduling.git
cd staff-scheduling

# 2. Create a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Copy the example env file and fill in your values
cp .env.example .env
```

### Docker setup (recommended)

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`.

---

## Environment Variables

Create a `.env` file in the project root. **Never commit this file.**

```env
# Required
SECRET_KEY=your-super-secret-key-min-32-chars
DATABASE_URL=postgresql://user:password@localhost:5432/staff_scheduling

# Optional (defaults shown)
APP_NAME="Staff Scheduling System"
APP_VERSION="0.1.0"
APP_ENV=development          # development | testing | production
LOG_LEVEL=info
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALGORITHM=HS256
ALLOWED_ORIGINS=http://localhost:3000
```

> `SECRET_KEY` and `DATABASE_URL` are required — the app will not start without them.

---

## Running the API

```bash
# From the project root
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Description |
|---|---|
| `http://localhost:8000/docs` | Swagger UI (disabled in production) |
| `http://localhost:8000/redoc` | ReDoc (disabled in production) |
| `http://localhost:8000/health` | Liveness probe |
| `http://localhost:8000/health/db` | Database readiness probe |

---

## Testing

The test suite enforces the **Testing Pyramid ratio**: 70% unit, 20% integration, 10% E2E.

```bash
# Run all tests with coverage
pytest

# Run only the unit layer
pytest tests/unit/

# Run only the integration layer
pytest tests/integration/

# Run with verbose output
pytest -v

# Run and see which lines are not covered
pytest --cov=backend/app --cov-report=term-missing
```

### Testing Pyramid

| Layer | Location | Tools | Isolation |
|---|---|---|---|
| Unit (70%) | `tests/unit/` | pytest, TestClient | No DB, no network — in-process only |
| Integration (20%) | `tests/integration/` | pytest, SQLite in-memory | Real ORM, real queries, no Postgres |
| E2E (10%) | `tests/e2e/` | Playwright, pytest-playwright | Full browser, real server (Phase 4) |

### How test isolation works

Every integration test runs inside a **SAVEPOINT** transaction that is rolled back after the test finishes. This means:

- Zero data pollution between tests
- No `DELETE FROM ...` teardown needed
- The in-memory SQLite DB is created once per session and dropped at the end

---

## CI/CD Pipeline

The GitHub Actions pipeline (`.github/workflows/ci.yml`) runs on every push and pull request.

```
Push / PR
    │
    ├── lint job  ────────────── ruff check + ruff format --check
    │
    └── test job
            ├── Unit tests     (tests/unit/)
            ├── Integration    (tests/integration/)
            └── Coverage XML   uploaded as artifact
```

The **lint** and **test** jobs run in parallel — a style violation blocks the pipeline without adding latency to the test run.

---

## API Reference

### Health endpoints

```
GET /health
```
Liveness probe — returns 200 as long as the process is alive.

```json
{
  "status": "ok",
  "service": "Staff Scheduling System",
  "version": "0.1.0",
  "environment": "development"
}
```

```
GET /health/db
```
Readiness probe — executes `SELECT 1` against the database.

```json
{ "status": "ok",       "database": "connected"   }   ← HTTP 200
{ "status": "degraded", "database": "unreachable" }   ← HTTP 503
```

### v1 endpoints (Phase 4)

```
POST   /api/v1/users/          Create user
GET    /api/v1/users/          List users
GET    /api/v1/users/{id}      Get user
PUT    /api/v1/users/{id}      Update user
DELETE /api/v1/users/{id}      Delete user

POST   /api/v1/shifts/         Create shift
GET    /api/v1/shifts/         List shifts
GET    /api/v1/shifts/{id}     Get shift
PUT    /api/v1/shifts/{id}     Update shift
DELETE /api/v1/shifts/{id}     Delete shift
```

---

## Design Constraints

These **Padlock rules** are enforced at the service layer and validated by the unit test suite:

| Constraint | Value |
|---|---|
| Minimum shift duration | 4 hours |
| Maximum shift duration | 12 hours |
| Maximum shifts per user per week | 5 |
| Maximum weekly hours per user | 40 hours |
| Minimum rest between shifts | 11 hours |

Violations return `HTTP 422 Unprocessable Entity` with a structured error body.

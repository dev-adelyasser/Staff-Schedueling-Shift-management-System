"""
tests/integration/test_users_api.py
─────────────────────────────────────
Integration tests for the User and Auth slices.

Testing Pyramid layer: INTEGRATION (20 %).
  • Real SQLite test.db — no mocking of the DB layer.
  • FastAPI TestClient with get_db() overridden to use a controlled session.
  • Each test runs inside a SAVEPOINT that is rolled back on teardown →
    perfect inter-test isolation at zero cost.

Known breakage until implementation is complete
───────────────────────────────────────────────
  ① repositories/__init__.py imports UserRepository (class) which was
    replaced with module-level functions — the whole app import chain will
    raise ImportError until that __init__ is updated.
  ② authenticate_user() in user_service.py is a TODO scaffold that always
    raises HTTP 401 — any test calling _login() will fail until filled in.
  ③ PATCH /api/v1/users/{id} does not exist yet — TestHR04 will fail with
    404/405 until the endpoint is added.
  ④ UserFactory.build() passes full_name= which is not a mapped column on
    the current User model (first_name/last_name split).  _seed_user() is
    used instead; UserFactory is imported per spec but cannot be called.

TDD contract: the tests below define what MUST be true once the
implementation is complete.  A failing test is a pending work item.
"""

# ── env vars MUST precede every `from app.*` import ───────────────────────────
import os
import sys
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "integration-test-secret-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("APP_ENV", "testing")

# Add workspace root so `tests.fixtures.factories` is importable.
# (backend/pyproject.toml only adds backend/ to sys.path; the factory lives
# one level up at <workspace>/tests/fixtures/factories.py.)
_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))
# ──────────────────────────────────────────────────────────────────────────────

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from app.database import Base as DbBase, get_db
from app.main import app
from app.models.user import Base as UserBase, User, UserRole
from app.core.security import hash_password

# Imported per spec.  Cannot be used until the factory's full_name field is
# aligned with the model's first_name / last_name columns — see note ④ above.
try:
    from tests.fixtures.factories import UserFactory  # noqa: F401
except ImportError:
    UserFactory = None  # type: ignore[assignment]


# ── Route constants ───────────────────────────────────────────────────────────
USERS = "/api/v1/users"
AUTH  = "/api/v1/auth/token"

# ── Shared passwords ──────────────────────────────────────────────────────────
_STAFF_PW = "Staff@9999!"
_ADMIN_PW = "Admin@9999!"
_NEW_PW   = "NewPass@2024!"


# =============================================================================
#  Database fixtures
# =============================================================================

# Single engine shared across the module.  File-based SQLite per spec.
_ENGINE = create_engine(
    "sqlite:///./test.db",
    connect_args={"check_same_thread": False},
    future=True,
)
_SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)


@pytest.fixture(scope="module", autouse=True)
def _create_tables():
    """Create all ORM tables once per module; drop them when the module ends.

    Two Base classes must both be created:
      • app.models.user.Base  — owns the users table
      • app.database.Base     — owns shifts and schedules tables
    Importing app.models ensures every model is registered on its metadata
    before create_all() is called.
    """
    import app.models  # noqa: F401 — registers User, Shift, Schedule

    UserBase.metadata.create_all(bind=_ENGINE)
    DbBase.metadata.create_all(bind=_ENGINE)
    yield
    DbBase.metadata.drop_all(bind=_ENGINE)
    UserBase.metadata.drop_all(bind=_ENGINE)


@pytest.fixture()
def db_session() -> Session:
    """Per-test DB session wrapped in a SAVEPOINT.

    The outer transaction is rolled back after each test — no data leaks
    between tests, and no explicit teardown SQL is required.
    """
    connection = _ENGINE.connect()
    transaction = connection.begin()
    session = _SessionFactory(bind=connection)
    session.begin_nested()  # SAVEPOINT

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        # Keep a live SAVEPOINT open for the next ORM flush.
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    """TestClient with get_db() overridden to use the test session.

    All FastAPI request handlers will hit the same in-memory transaction
    that db_session controls, so data seeded via _seed_user() is visible
    to the HTTP layer without committing.
    """
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# =============================================================================
#  Helpers
# =============================================================================

def _seed_user(
    db: Session,
    *,
    email: str,
    password: str = _STAFF_PW,
    role: UserRole = UserRole.STAFF,
) -> User:
    """Insert a fully-formed User row directly into the test DB session.

    Bypasses UserFactory because UserFactory.build() sets full_name which
    is absent from the current User ORM model (schema-model gap, note ④).
    Sets token_version=1 to match create_user() service behaviour (HR-04).
    """
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        first_name="",
        last_name="",
        role=role,
        token_version=1,
        is_deleted=False,
    )
    db.add(user)
    db.flush()
    return user


def _login(client: TestClient, email: str, password: str) -> str:
    """POST credentials to the auth endpoint and return the raw access_token.

    Will raise AssertionError if the endpoint returns non-200 (e.g. while
    authenticate_user() is still a TODO scaffold — see note ② above).
    """
    resp = client.post(AUTH, json={"email": email, "password": password})
    assert resp.status_code == 200, (
        f"Login failed [{resp.status_code}]: {resp.json()}. "
        "Ensure authenticate_user() TODO in user_service.py is completed."
    )
    return resp.json()["access_token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
#  Test: POST /api/v1/users/
# =============================================================================

@pytest.mark.integration
class TestCreateUser:

    def test_returns_201_and_hides_hashed_password(self, client):
        """POST /users/ must create a user (201) and never expose hashed_password.

        Information Hiding invariant (AU-02): the hashed credential must be
        stripped by UserResponseSchema — it must not appear in any key of the
        JSON response, even with a different name.
        """
        payload = {
            "email": "create_test@example.com",
            "password": _STAFF_PW,
            "role": "STAFF",
        }

        resp = client.post(USERS + "/", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == payload["email"]
        # Hard security guards — any appearance of these keys is a leak.
        assert "hashed_password" not in data
        assert "token_version" not in data


# =============================================================================
#  Test: POST /api/v1/auth/token
# =============================================================================

@pytest.mark.integration
class TestAuthToken:

    def test_valid_credentials_return_200_and_access_token(self, client, db_session):
        """Correct email + password must yield HTTP 200 with an access_token field.

        Depends on authenticate_user() TODO being completed (note ②).
        """
        _seed_user(db_session, email="auth_ok@example.com", password=_STAFF_PW)

        resp = client.post(AUTH, json={
            "email": "auth_ok@example.com",
            "password": _STAFF_PW,
        })

        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body.get("token_type", "").lower() == "bearer"

    def test_wrong_password_returns_401(self, client, db_session):
        """Any credential mismatch must produce HTTP 401.

        The response must NOT distinguish between unknown email and wrong
        password (enumeration-safe per AU-03).
        """
        _seed_user(db_session, email="auth_bad@example.com", password=_STAFF_PW)

        resp = client.post(AUTH, json={
            "email": "auth_bad@example.com",
            "password": "TotallyWrong@000",
        })

        assert resp.status_code == 401


# =============================================================================
#  Test: GET /api/v1/users/{id}
# =============================================================================

@pytest.mark.integration
class TestGetUserById:

    def test_no_token_returns_401(self, client, db_session):
        """Unauthenticated request must be rejected with HTTP 401.

        OAuth2PasswordBearer raises 401 before the handler runs — no user
        is needed in the DB for this test.
        """
        resp = client.get(f"{USERS}/999")

        assert resp.status_code == 401

    def test_staff_token_for_other_user_returns_403(self, client, db_session):
        """A STAFF user requesting another user's profile must receive HTTP 403.

        Router rule: current.id != user_id AND role not in (MANAGER, ADMIN) → 403.
        Depends on authenticate_user() TODO being completed (note ②).
        """
        admin = _seed_user(
            db_session,
            email="profile_owner@example.com",
            password=_ADMIN_PW,
            role=UserRole.ADMIN,
        )
        _seed_user(
            db_session,
            email="staff_viewer@example.com",
            password=_STAFF_PW,
            role=UserRole.STAFF,
        )
        db_session.flush()

        staff_token = _login(client, "staff_viewer@example.com", _STAFF_PW)
        resp = client.get(
            f"{USERS}/{admin.id}",
            headers=_bearer(staff_token),
        )

        assert resp.status_code == 403

    def test_admin_token_returns_200_with_user_data(self, client, db_session):
        """An ADMIN can fetch any user profile → HTTP 200 with correct id.

        Depends on authenticate_user() TODO being completed (note ②).
        """
        target = _seed_user(
            db_session,
            email="profile_target@example.com",
            password=_STAFF_PW,
            role=UserRole.STAFF,
        )
        _seed_user(
            db_session,
            email="requesting_admin@example.com",
            password=_ADMIN_PW,
            role=UserRole.ADMIN,
        )
        db_session.flush()

        admin_token = _login(client, "requesting_admin@example.com", _ADMIN_PW)
        resp = client.get(
            f"{USERS}/{target.id}",
            headers=_bearer(admin_token),
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == target.id
        # Confirm the response schema never leaks internal fields.
        assert "hashed_password" not in resp.json()
        assert "token_version" not in resp.json()


# =============================================================================
#  Test: HR-04 — PATCH /api/v1/users/{id} invalidates old tokens
# =============================================================================

@pytest.mark.integration
class TestHR04TokenInvalidationOnPasswordChange:
    """
    HR-04: changing a password must invalidate all previously issued JWTs
    by incrementing token_version in the DB.

    Depends on:
      • authenticate_user() TODO being completed (note ②).
      • PATCH /api/v1/users/{id} endpoint being implemented (note ③).
        Until then this test fails at step 2 with a 404/405.
    """

    def test_old_token_rejected_after_password_change(self, client, db_session):
        """
        Flow:
          1. Seed an ADMIN user; obtain token_v1 via POST /auth/token.
          2. PATCH /users/{id} with a new password — this must increment
             token_version in the DB (update_user() service).
          3. Re-use token_v1 on GET /users/{id} — must receive HTTP 401
             with a detail message containing 'invalidated' (HR-04 guard in
             get_current_user() dependency).
        """
        user = _seed_user(
            db_session,
            email="hr04_user@example.com",
            password=_STAFF_PW,
            role=UserRole.ADMIN,  # admin so the GET in step 3 would pass RBAC
        )
        db_session.flush()

        # Step 1 — capture the original JWT (token_version = 1)
        token_v1 = _login(client, "hr04_user@example.com", _STAFF_PW)

        # Step 2 — change the password; update_user() must bump token_version to 2
        patch_resp = client.patch(
            f"{USERS}/{user.id}",
            json={"id": user.id, "password": _NEW_PW},
            headers=_bearer(token_v1),
        )
        assert patch_resp.status_code == 200, (
            f"PATCH returned {patch_resp.status_code}: {patch_resp.json()}. "
            "Add PATCH /api/v1/users/{{id}} endpoint — see note ③."
        )

        # Step 3 — the original token must now be rejected (HR-04)
        get_resp = client.get(
            f"{USERS}/{user.id}",
            headers=_bearer(token_v1),
        )
        assert get_resp.status_code == 401
        detail = get_resp.json().get("detail", "")
        assert "invalidated" in detail.lower(), (
            f"Expected 'invalidated' in 401 detail, got: {detail!r}"
        )

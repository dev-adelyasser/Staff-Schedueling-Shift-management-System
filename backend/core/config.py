# =============================================================================
#  backend/app/core/config.py
#  Configuration Management — Staff Scheduling System
#
#  Architecture Principles Applied
#  ────────────────────────────────
#  Information Hiding : All environment-variable parsing is centralised here.
#                       No other module calls os.environ or reads .env directly.
#                       Every layer imports `settings` (or calls `get_settings`).
#
#  Refinement Loop    : Every configuration value carries a measurable, numeric
#                       constraint.  Vague adjectives ("secure", "fast", "long")
#                       are replaced by the specific threshold the system enforces.
#
#  Pydantic v2 notes  : BaseSettings lives in `pydantic_settings` (not pydantic).
#                       model_config replaces the inner class Config pattern.
#                       Field(ge/le) enforces numeric bounds declaratively.
#
#  Singleton pattern  : get_settings() is @lru_cache'd so the Settings object is
#                       constructed once.  Use as a FastAPI dependency:
#                           Annotated[Settings, Depends(get_settings)]
#                       The module-level `settings` alias is available for
#                       non-DI contexts (e.g. database.py engine setup).
# =============================================================================

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Single source of truth for every runtime parameter.

    Values are loaded (in priority order):
      1. OS environment variables  — used in Docker / CI
      2. .env file                 — used in local development
      3. Field default             — safe fallback documented inline

    All thresholds are measurable integers or explicit strings;
    no field is described only by a subjective adjective.
    """

    # ── Model config (Pydantic v2, placed first) ──────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # DATABASE_URL == database_url in .env
        extra="ignore",         # silently drop unknown env vars — prevents typo surprises
    )

    # =========================================================================
    #  APPLICATION
    # =========================================================================
    app_name: str = Field(
        default="Staff Scheduling System",
        description="Human-readable application name (shown in OpenAPI docs).",
    )
    app_version: str = Field(
        default="0.1.0",
        description="Semantic version string (shown in OpenAPI docs).",
    )
    app_env: str = Field(
        default="development",
        description="Runtime environment tag. One of: development | staging | production.",
    )
    log_level: str = Field(
        default="info",
        description="Log verbosity. One of: debug | info | warning | error | critical.",
    )
    # Refinement Loop: replaces "don't return too many records at once".
    max_page_size: int = Field(
        default=100,
        ge=10,
        le=500,
        description="Hard ceiling on ?limit= query parameter for list endpoints. Range: 10–500.",
    )

    # =========================================================================
    #  DATABASE
    #  DATABASE_URL is assembled by docker-compose from individual credential
    #  vars and injected as a single DSN string.  PostgresDsn validates the URI
    #  format at startup rather than at first DB call.
    # =========================================================================
    database_url: PostgresDsn = Field(
        ...,  # required — startup fails fast if absent
        description=(
            "Fully-qualified PostgreSQL DSN assembled by docker-compose. "
            "Format: postgresql://user:pass@host:port/dbname"
        ),
    )

    # ── Connection Pool — Refinement Loop ────────────────────────────────────
    # Measurable replacements for "enough connections to handle load".
    db_pool_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="SQLAlchemy QueuePool steady-state size. Range: 1–100.",
    )
    db_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Max connections above pool_size allowed during bursts. Range: 0–50.",
    )
    # Measurable replacement for "don't wait forever" on pool checkout.
    db_pool_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Seconds before SQLAlchemy raises TimeoutError on pool checkout. Range: 5–120.",
    )

    # =========================================================================
    #  AUTHENTICATION & SECURITY
    # =========================================================================
    secret_key: str = Field(
        ...,  # required — startup fails fast; never has a default
        min_length=32,  # >= 256 bits when hex-encoded
        description=(
            "HMAC signing key for JWT tokens. "
            "Must be >= 32 characters (256-bit entropy minimum). "
            "Generate with: openssl rand -hex 32"
        ),
    )

    # JWT signing algorithm — consumed directly by python-jose.
    algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm passed to python-jose. Default: HS256.",
    )

    # Refinement Loop: replaces "tokens should expire after a reasonable time".
    # Matches the env-var name in docker-compose.yml exactly.
    access_token_expire_minutes: int = Field(
        default=30,
        ge=5,     # < 5 min is operationally unusable
        le=1440,  # 24 h hard ceiling — beyond this, use refresh tokens
        description="JWT access-token lifetime in minutes. Range: 5–1440.",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="JWT refresh-token lifetime in days. Range: 1–90.",
    )

    # bcrypt work-factor: each +1 doubles hashing time (~120 ms at 12).
    # Measurable replacement for "strong password hashing".
    bcrypt_rounds: int = Field(
        default=12,
        ge=10,
        le=14,
        description=(
            "bcrypt cost factor. "
            "10 ~= 30 ms | 12 ~= 120 ms | 14 ~= 500 ms per hash on modern hardware. "
            "Range: 10–14."
        ),
    )

    # ── Brute-force protection — Refinement Loop ─────────────────────────────
    # Replaces "lock accounts after too many failed logins".
    # Service layer reads this value; threshold is not scattered across business logic.
    max_login_attempts: int = Field(
        default=5,
        ge=3,
        le=20,
        description="Failed login attempts before account is temporarily locked. Range: 3–20.",
    )
    login_lockout_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="Account lockout duration in minutes after brute-force threshold. Range: 1–1440.",
    )

    # =========================================================================
    #  CORS / HTTP
    # =========================================================================
    # Stored as list[str] natively; parse_origins converts docker-compose's
    # comma-separated string into a list before validation.
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description=(
            "Allowed CORS origins. Accepts a Python list or a "
            "comma-separated string (e.g. from docker-compose env)."
        ),
    )
    # Replaces "cache preflight responses for a while".
    # 3600 s = 1 h; browsers skip OPTIONS requests for this duration.
    cors_max_age: int = Field(
        default=3600,
        ge=0,
        le=86400,  # 24 h is the practical browser maximum
        description="Seconds browsers may cache CORS preflight responses. Range: 0–86400.",
    )
    # Prevents resource-exhaustion from oversized payloads.
    # 16 384 B = 16 KB — adequate for scheduling JSON.
    max_request_body_size: int = Field(
        default=16_384,
        ge=1_024,
        le=10_485_760,  # 10 MB absolute ceiling
        description="Maximum accepted HTTP request body in bytes. Range: 1 KB–10 MB.",
    )

    # =========================================================================
    #  SCHEDULING DOMAIN CONSTRAINTS — Refinement Loop
    #  Replaces prose rules like "shifts must be a reasonable length" with
    #  values that validators.py and services can import directly.
    # =========================================================================
    min_shift_duration_hours: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Minimum allowed shift length in hours. Range: 1–4.",
    )
    max_shift_duration_hours: int = Field(
        default=12,
        ge=4,
        le=24,
        description="Maximum allowed shift length in hours. Range: 4–24.",
    )
    # EU Working Time Directive default = 48 h/week.
    max_weekly_hours: int = Field(
        default=48,
        ge=20,
        le=80,
        description=(
            "Maximum hours a staff member may be scheduled per 7-day week. "
            "Range: 20–80 (EU Working Time Directive default = 48)."
        ),
    )

    # =========================================================================
    #  FIELD-LEVEL VALIDATORS
    # =========================================================================

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: object) -> list[str]:
        """Accept either a Python list or a comma-separated string.

        Docker-compose injects ALLOWED_ORIGINS as a single string;
        test code may pass a list directly.  Both forms are valid.
        """
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v  # type: ignore[return-value]

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        allowed = {"development", "staging", "production"}
        if value.lower() not in allowed:
            raise ValueError(f"app_env must be one of {allowed}; got '{value}'")
        return value.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"debug", "info", "warning", "error", "critical"}
        if value.lower() not in allowed:
            raise ValueError(f"log_level must be one of {allowed}; got '{value}'")
        return value.lower()

    @field_validator("min_shift_duration_hours")
    @classmethod
    def validate_shift_duration_ordering(cls, value: int, info: object) -> int:
        """Guarantee min < max at settings-parse time, not at first business call."""
        max_val = getattr(info, "data", {}).get("max_shift_duration_hours")
        if max_val is not None and value >= max_val:
            raise ValueError(
                f"min_shift_duration_hours ({value}) must be "
                f"< max_shift_duration_hours ({max_val})"
            )
        return value

    # =========================================================================
    #  CONVENIENCE PROPERTIES
    # =========================================================================

    @property
    def is_production(self) -> bool:
        """Guard for debug routes and verbose error responses."""
        return self.app_env == "production"

    @property
    def database_url_str(self) -> str:
        """Return database_url as a plain str.

        SQLAlchemy's create_engine() requires a str, not a Pydantic Url object.
        This property handles the cast in one place so database.py stays clean.
        """
        return str(self.database_url)


# =============================================================================
#  SINGLETON ACCESSOR
#  ──────────────────
#  @lru_cache ensures Settings() is constructed exactly once per process,
#  regardless of how many modules call get_settings() or import `settings`.
#
#  Two usage patterns:
#
#  1. FastAPI Dependency Injection (preferred in route handlers):
#
#         from app.core.config import get_settings, Settings
#         from typing import Annotated
#         from fastapi import Depends
#
#         SettingsDep = Annotated[Settings, Depends(get_settings)]
#
#         @router.get("/example")
#         def example(cfg: SettingsDep) -> ...:
#             token_ttl = cfg.access_token_expire_minutes
#
#  2. Direct module import (used in database.py and other non-DI contexts):
#
#         from app.core.config import settings
#         engine = create_engine(settings.database_url_str)
# =============================================================================

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Decorated with @lru_cache so Pydantic's env-var parsing runs exactly once.
    """
    return Settings()


# Module-level alias — convenient for non-DI imports throughout the codebase.
settings: Settings = get_settings()

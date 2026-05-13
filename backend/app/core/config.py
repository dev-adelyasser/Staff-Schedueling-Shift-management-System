"""
app/core/config.py
──────────────────
Centralised settings loaded from environment variables / .env file.
Using pydantic-settings so every value is type-validated at startup.

Information Hiding: only this module ever reads raw env vars.
All other layers import `settings` and never call os.environ directly.
"""

from functools import lru_cache
from pydantic import AnyUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ───────────────────────────────────────────
    app_name: str = "Staff Scheduling System"
    app_version: str = "0.1.0"
    app_env: str = "development"
    log_level: str = "info"

    # ── Security ──────────────────────────────────────────────
    secret_key: str
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    # ── Database ──────────────────────────────────────────────
    database_url: str

    # ── CORS ──────────────────────────────────────────────────
    allowed_origins: list[str] = ["http://localhost:3000"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        """Accept either a list or a comma-separated string."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# ── Singleton accessor (cached) ───────────────────────────────
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached Settings instance.
    Use as a FastAPI dependency: Depends(get_settings)
    """
    return Settings()


# Convenient module-level alias used across the codebase
settings: Settings = get_settings()

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# Single declarative base — defined in user.py to avoid a circular-import;
# re-exported here so every other module can do `from app.database import Base`.
from app.models.user import Base  # noqa: F401

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    echo=(settings.app_env == "development"),
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Only for test conftest.py — never wired to the app lifespan
def create_all_tables() -> None:
    Base.metadata.create_all(bind=engine)


def drop_all_tables() -> None:
    Base.metadata.drop_all(bind=engine)

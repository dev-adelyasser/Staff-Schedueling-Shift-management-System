from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Shared Base for models
class Base(DeclarativeBase):
    pass

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    STAFF = "STAFF"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # AU-02 Spec: bcrypt hashes are 60 chars; pinned to VARCHAR(72) to match exact spec limits
    hashed_password: Mapped[str] = mapped_column(String(72), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.STAFF, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    token_version: Mapped[int] = mapped_column(default=0, nullable=False)
    
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    if TYPE_CHECKING:
        from app.models.shift import Shift
        shifts: Mapped[list["Shift"]] = relationship(back_populates="user")

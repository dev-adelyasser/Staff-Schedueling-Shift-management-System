"""add user security columns and fix shift schema

Revision ID: a1b2c3d4e5f6
Revises: 3fd1bbe6137a
Create Date: 2024-01-01 00:00:00.000000

Covers:
- users: token_version, is_deleted, deleted_at, hashed_password widened to 72
- shifts: is_deleted, deleted_at, created_by FK, department_id, headcount
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "a1b2c3d4e5f6"
down_revision = "3fd1bbe6137a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # users table
    # ------------------------------------------------------------------ #

    # HR-04: token versioning
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )

    # Soft delete
    op.add_column(
        "users",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # AU-02: bcrypt hashes are 60 chars; spec pins VARCHAR(72)
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(128),
        type_=sa.String(72),
        existing_nullable=False,
    )

    # ------------------------------------------------------------------ #
    # shifts table
    # ------------------------------------------------------------------ #

    # Soft delete
    op.add_column(
        "shifts",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "shifts",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Spec section 10: required shift fields
    op.add_column(
        "shifts",
        sa.Column("department_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "shifts",
        sa.Column("headcount", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "shifts",
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # ix_shifts_staff_id is created in the Person-2 migration once staff_assignments
    # replaces the old per-row staff_id column (staff_id lives in staff_assignments).


def downgrade() -> None:
    op.drop_column("shifts", "created_by")
    op.drop_column("shifts", "headcount")
    op.drop_column("shifts", "department_id")
    op.drop_column("shifts", "deleted_at")
    op.drop_column("shifts", "is_deleted")

    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(72),
        type_=sa.String(128),
        existing_nullable=False,
    )
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "is_deleted")
    op.drop_column("users", "token_version")

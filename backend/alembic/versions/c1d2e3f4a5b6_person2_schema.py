"""Person 2 schema: rebuild shifts (UUID PK), add staff_assignments, audit_logs,
swap_requests, staff_availability, attendance_records.

Revision ID: c1d2e3f4a5b6
Revises: d4e5f6a1b2c3
Create Date: 2026-05-20 00:00:00.000000

Design notes:
  - shifts.id is now a server-generated UUID (gen_random_uuid()).
  - Staff assignments live in staff_assignments; shifts no longer carry user_id.
  - audit_logs.target_id is UUID to cover both shift and swap targets.
  - swap_requests uses a native ENUM for three-state machine (AU-08).
  - All JSONB columns require PostgreSQL 9.4+; this project targets PG 15.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "d4e5f6a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Drop old shifts table (INTEGER PK, wrong schema) and recreate      #
    # ------------------------------------------------------------------ #
    op.drop_table("shifts")

    op.create_table(
        "shifts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("headcount", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_shifts_department_id", "shifts", ["department_id"])
    op.create_index("ix_shifts_is_deleted", "shifts", ["is_deleted"])

    # ------------------------------------------------------------------ #
    # staff_assignments — AU-04 overlap queries filter on staff_id index  #
    # ------------------------------------------------------------------ #
    op.create_table(
        "staff_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "shift_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "staff_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assigned_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("shift_id", "staff_id", name="uq_staff_assignment_shift_staff"),
    )
    op.create_index("ix_staff_assignments_shift_id", "staff_assignments", ["shift_id"])
    # AU-04: this index is the anchor for the single-query overlap predicate
    op.create_index("ix_staff_assignments_staff_id", "staff_assignments", ["staff_id"])

    # ------------------------------------------------------------------ #
    # audit_logs — AU-07 immutable trail                                  #
    # ------------------------------------------------------------------ #
    op.execute("CREATE TYPE audit_action_type AS ENUM ('CREATE', 'UPDATE', 'DELETE')")

    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "action_type",
            postgresql.ENUM(
                "CREATE", "UPDATE", "DELETE",
                name="audit_action_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("target_table", sa.String(64), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("before_state", postgresql.JSONB, nullable=True),
        sa.Column("after_state", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])

    # ------------------------------------------------------------------ #
    # swap_requests — AU-08 three-state machine                           #
    # ------------------------------------------------------------------ #
    op.execute("CREATE TYPE swap_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED')")

    op.create_table(
        "swap_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "requester_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requester_shift_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_shift_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "APPROVED", "REJECTED",
                name="swap_status",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_swap_requests_requester_id", "swap_requests", ["requester_id"])
    op.create_index("ix_swap_requests_status", "swap_requests", ["status"])

    # ------------------------------------------------------------------ #
    # staff_availability — Slice 4                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "staff_availability",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "staff_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "is_available",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.UniqueConstraint("staff_id", "day_of_week", name="uq_availability_staff_day"),
    )
    op.create_index("ix_staff_availability_staff_id", "staff_availability", ["staff_id"])

    # ------------------------------------------------------------------ #
    # attendance_records — Slice 5 (Clock In/Out)                        #
    # ------------------------------------------------------------------ #
    op.execute(
        "CREATE TYPE attendance_status AS ENUM "
        "('ON_TIME', 'LATE', 'EARLY_DEPARTURE', 'ABSENT')"
    )

    op.create_table(
        "attendance_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "staff_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shift_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("shifts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("clock_in", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "ON_TIME", "LATE", "EARLY_DEPARTURE", "ABSENT",
                name="attendance_status",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index("ix_attendance_records_staff_id", "attendance_records", ["staff_id"])
    op.create_index("ix_attendance_records_shift_id", "attendance_records", ["shift_id"])


def downgrade() -> None:
    op.drop_table("attendance_records")
    op.execute("DROP TYPE IF EXISTS attendance_status")

    op.drop_table("staff_availability")

    op.drop_table("swap_requests")
    op.execute("DROP TYPE IF EXISTS swap_status")

    op.drop_table("audit_logs")
    op.execute("DROP TYPE IF EXISTS audit_action_type")

    op.drop_table("staff_assignments")

    op.drop_table("shifts")

    # Restore the original shifts table (INTEGER PK, legacy shape)
    op.create_table(
        "shifts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("headcount", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )

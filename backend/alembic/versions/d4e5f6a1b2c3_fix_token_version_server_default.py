"""fix token_version server default from 0 to 1

Revision ID: d4e5f6a1b2c3
Revises: a1b2c3d4e5f6
Create Date: 2026-05-20 00:00:00.000000

Audit finding
─────────────
Migration a1b2c3d4e5f6 added token_version with server_default="0".
The spec requires DEFAULT 1 so that any row inserted without an explicit
token_version value (e.g. seed scripts, DBA backfills) starts at 1, which
matches the version embedded in the first JWT issued by create_user().

A server_default of 0 means a directly-inserted user would have
token_version=0 in the DB while every JWT carries ver=1, permanently
locking that user out of the HR-04 validation in get_current_user().

Columns confirmed present by this audit (no action needed)
──────────────────────────────────────────────────────────
  ✓ is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
  ✓ deleted_at  TIMESTAMPTZ nullable

Column corrected by this migration
───────────────────────────────────
  token_version  INTEGER NOT NULL  server_default 0 → 1
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a1b2c3"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change the column-level server default from 0 to 1.
    # Existing rows are NOT back-filled — their token_version was already set
    # to 1 by create_user() at insert time (Python-level assignment).
    # Only net-new rows inserted without an explicit value are affected.
    op.alter_column(
        "users",
        "token_version",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default="1",
    )


def downgrade() -> None:
    # Restore the previous (incorrect) server default of 0.
    op.alter_column(
        "users",
        "token_version",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default="0",
    )

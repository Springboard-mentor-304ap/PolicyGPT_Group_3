"""Add email verification to users and create role_requests table

Revision ID: a1b2c3d4e5f6
Revises: 14163ed40e42
Create Date: 2026-09-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "a1b2c3d4e5f6"
down_revision = "14163ed40e42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Add email verification columns to users ──────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("email_verification_token", sa.String(500), nullable=True),
    )

    # ── 2. Add new UPPERCASE values to user_role enum ──────────────────────
    # The original migration created user_role with UPPERCASE values
    # (ADMIN, GOVERNMENT_OFFICIAL, CITIZEN, RESEARCHER, ORGANIZATION).
    # SQLAlchemy's SQLEnum maps Python enum .name (UPPERCASE) to the DB,
    # so we only need to add the two new role names.
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'ADMINISTRATOR'")
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'SUPER_ADMIN'")

    # ── 3. Create role_requests enums via raw SQL (idempotent) ─────────────
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE requested_role AS ENUM "
        "('researcher','organization','government_official','administrator'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE request_status AS ENUM "
        "('pending','approved','rejected','cancelled'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    # ── 4. Create role_requests table using raw SQL ─────────────────────────
    op.execute("""
        CREATE TABLE role_requests (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            requested_role requested_role NOT NULL,
            status      request_status NOT NULL DEFAULT 'pending',
            details     JSONB,
            review_reason TEXT,
            reviewer_id UUID REFERENCES users(id),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            reviewed_at TIMESTAMPTZ
        )
    """)

    # Indexes
    op.create_index("ix_role_requests_user_id", "role_requests", ["user_id"])
    op.create_index("ix_role_requests_status", "role_requests", ["status"])
    op.create_index(
        "ix_role_requests_user_status",
        "role_requests",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_table("role_requests")
    op.execute("DROP TYPE IF EXISTS request_status")
    op.execute("DROP TYPE IF EXISTS requested_role")
    op.drop_column("users", "email_verification_token")
    op.drop_column("users", "email_verified")

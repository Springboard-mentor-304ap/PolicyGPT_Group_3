"""harden auth tokens and application uniqueness

Adds the storage for single-use password reset tokens (a sha256 hash of the
token's `jti` plus its expiry, mirroring `email_verification_token`) and the
database-level guarantees behind two API fixes:

* `uix_users_email_lower` — e-mails are case-insensitive, so the database
  enforces one account per address regardless of case. Existing addresses are
  normalized to lowercase first; the migration aborts instead of deleting
  accounts if two rows already collide.
* `uix_applications_user_scheme` — one application per user and scheme, so
  the service's check-then-insert cannot race into a duplicate.

Revision ID: e5f6a7b8c9d0
Revises: c7f1a2b3d4e5
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "c7f1a2b3d4e5"
branch_labels = None
depends_on = None


def _assert_no_duplicates(table: str, expression: str, label: str) -> None:
    """Abort with a clear message instead of silently deleting user data."""
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            f"SELECT {expression}, count(*) FROM {table} "
            f"GROUP BY {expression} HAVING count(*) > 1 LIMIT 5"
        )
    ).fetchall()

    if duplicates:
        raise RuntimeError(
            f"Cannot create the unique constraint for {label}: the existing "
            f"data contains duplicates {duplicates!r}. Resolve them before "
            "running this migration."
        )


def upgrade() -> None:
    # ── 1. Single-use password reset tokens ─────────────────────────────────
    op.execute(
        "ALTER TABLE users "
        "ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(500)"
    )

    # ── 2. Case-insensitive e-mail uniqueness ───────────────────────────────
    _assert_no_duplicates("users", "lower(email)", "users.email")

    op.execute(
        "UPDATE users SET email = lower(email) "
        "WHERE email IS NOT NULL AND email <> lower(email)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uix_users_email_lower "
        "ON users (lower(email))"
    )

    # ── 3. One application per user and scheme ──────────────────────────────
    _assert_no_duplicates(
        "applications",
        "user_id, scheme_id",
        "applications(user_id, scheme_id)",
    )

    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uix_applications_user_scheme "
        "ON applications (user_id, scheme_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uix_applications_user_scheme")
    op.execute("DROP INDEX IF EXISTS uix_users_email_lower")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS password_reset_token")

"""add email verification attempt tracking

Adds two nullable columns to users, so the migration works on a database
that already has rows (no backfill needed: NULL means "no pending code /
no cooldown"):

* ``email_verification_attempts`` — wrong-guess counter for the pending
  6-digit code; the code is invalidated after too many wrong guesses.
* ``email_verification_sent_at``  — when the pending code was issued
  (UTC); backs the 60-second resend cooldown.

Revision ID: g4b5c6d7e8f9
Revises: f3a1b2c4d5e6
Create Date: 2026-10-15
"""

from alembic import op


revision = "g4b5c6d7e8f9"
down_revision = "f3a1b2c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE users "
        "ADD COLUMN IF NOT EXISTS email_verification_attempts INTEGER"
    )
    op.execute(
        "ALTER TABLE users "
        "ADD COLUMN IF NOT EXISTS email_verification_sent_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS email_verification_sent_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS email_verification_attempts")

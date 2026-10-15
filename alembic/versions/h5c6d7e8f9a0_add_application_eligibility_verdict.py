"""add advisory eligibility verdict to applications

Nullable column recording what the eligibility engine said about the
applicant's profile at submission time. Advisory only: it never blocks an
application and is never trusted from the client — the server computes it.
NULL means the verdict could not be computed (profile missing, scheme has
no rules, or the check failed).

Revision ID: h5c6d7e8f9a0
Revises: g4b5c6d7e8f9
Create Date: 2026-10-15
"""

from alembic import op


revision = "h5c6d7e8f9a0"
down_revision = "g4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE applications "
        "ADD COLUMN IF NOT EXISTS eligibility_verdict VARCHAR(50)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE applications DROP COLUMN IF EXISTS eligibility_verdict"
    )

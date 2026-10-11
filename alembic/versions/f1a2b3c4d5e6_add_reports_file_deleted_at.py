"""add reports.file_deleted_at retention marker

Revision ID: f1a2b3c4d5e6
Revises: b7e1c9a4d2f6
Create Date: 2026-10-11 00:00:00.000000

The cleanup task deletes generated report files once they are older than
REPORT_RETENTION_DAYS and stamps the row with the deletion time so the
download endpoint can answer 410 Gone instead of an ambiguous 404.

The column is nullable and added without a default, so every existing row
stays valid (NULL simply means "file not expired yet").
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'b7e1c9a4d2f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Purely additive: no backfill, no lock-heavy rewrite, safe on a table
    that already holds rows.
    """
    op.add_column(
        'reports',
        sa.Column(
            'file_deleted_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('reports', 'file_deleted_at')

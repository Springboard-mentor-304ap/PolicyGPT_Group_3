"""add application withdrawn status

Revision ID: a9f0c1d2e3b4
Revises: 57c8d8e4ecf5
Create Date: 2026-10-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9f0c1d2e3b4'
down_revision: Union[str, Sequence[str], None] = '57c8d8e4ecf5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add WITHDRAWN to application_status.

    Appends a label to the existing enum — safe on a table that already has
    data (existing rows and values are untouched). Mirrors the pattern of
    b2c3d4e5f6a7.
    """
    op.execute("ALTER TYPE application_status ADD VALUE IF NOT EXISTS 'WITHDRAWN'")


def downgrade() -> None:
    """PostgreSQL does not support removing enum values.
    To downgrade, the enum type would need to be recreated."""
    pass

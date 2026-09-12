"""add scheme approval status values

Revision ID: b2c3d4e5f6a7
Revises: 75beb90c030a
Create Date: 2026-09-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = '75beb90c030a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add PENDING_APPROVAL and REJECTED values to scheme_status enum."""
    op.execute("ALTER TYPE scheme_status ADD VALUE IF NOT EXISTS 'PENDING_APPROVAL'")
    op.execute("ALTER TYPE scheme_status ADD VALUE IF NOT EXISTS 'REJECTED'")


def downgrade() -> None:
    """PostgreSQL does not support removing enum values.
    To downgrade, the enum type would need to be recreated."""
    pass

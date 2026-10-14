"""add eligibility state district

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-13 10:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add STATE and DISTRICT values to eligibility_parameter enum."""
    op.execute("ALTER TYPE eligibility_parameter ADD VALUE IF NOT EXISTS 'STATE'")
    op.execute("ALTER TYPE eligibility_parameter ADD VALUE IF NOT EXISTS 'DISTRICT'")


def downgrade() -> None:
    """PostgreSQL does not support removing enum values.
    To downgrade, the enum type would need to be recreated."""
    pass

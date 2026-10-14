"""add scheme approval fields

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-13 10:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add approved_by and rejection_reason columns to schemes."""
    op.add_column('schemes', sa.Column('approved_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('schemes', sa.Column('rejection_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove approved_by and rejection_reason columns from schemes."""
    op.drop_column('schemes', 'rejection_reason')
    op.drop_column('schemes', 'approved_by')

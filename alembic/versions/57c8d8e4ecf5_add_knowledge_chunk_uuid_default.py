"""add knowledge chunk uuid default

Revision ID: 57c8d8e4ecf5
Revises: 64f7d126000c
Create Date: 2026-10-08 02:34:31.421069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57c8d8e4ecf5'
down_revision: Union[str, Sequence[str], None] = '64f7d126000c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "knowledge_chunks",
        "id",
        server_default=sa.text("gen_random_uuid()"),
    )


def downgrade() -> None:
    op.alter_column(
        "knowledge_chunks",
        "id",
        server_default=None,
    )

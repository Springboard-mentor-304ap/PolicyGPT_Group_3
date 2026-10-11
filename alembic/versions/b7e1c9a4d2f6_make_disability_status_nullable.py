"""make user profile disability_status nullable

Revision ID: b7e1c9a4d2f6
Revises: a9f0c1d2e3b4
Create Date: 2026-10-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e1c9a4d2f6'
down_revision: Union[str, Sequence[str], None] = 'a9f0c1d2e3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Existing rows are left exactly as they are (a stored False stays False);
    only the column definition changes so NULL can now mean "never answered".
    The server default is dropped so newly inserted profiles that omit the
    flag get NULL instead of a fabricated False.
    """
    op.alter_column(
        'user_profiles',
        'disability_status',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    """Downgrade schema.

    The old column was NOT NULL, so rows that were never answered are set
    back to its server default before the column is tightened again.
    """
    op.execute(
        "UPDATE user_profiles SET disability_status = false "
        "WHERE disability_status IS NULL"
    )
    op.alter_column(
        'user_profiles',
        'disability_status',
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text('false'),
    )

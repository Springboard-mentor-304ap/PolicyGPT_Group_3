"""add refresh_tokens table

Revision ID: d8e4f5a6b7c8
Revises: a3c9d1e5f7b2
Create Date: 2026-10-11

Only the SHA-256 hash of each refresh token's jti is stored, mirroring the
password-reset token convention; a leaked database never contains a usable
token. Purely additive (new table + indexes), so it is safe on a database
that already holds data.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d8e4f5a6b7c8"
down_revision: Union[str, None] = "a3c9d1e5f7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
    )
    # One hash per token: the lookup path for rotation and reuse detection.
    op.create_index(
        "ix_refresh_tokens_jti_hash",
        "refresh_tokens",
        ["jti_hash"],
        unique=True,
    )


def downgrade() -> None:
    # Dropping the table loses the live sessions, which is the correct
    # direction for a downgrade: the tokens would otherwise be unrevocable.
    op.drop_index("ix_refresh_tokens_jti_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

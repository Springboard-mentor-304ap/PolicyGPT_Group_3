"""Add content_views table for one-view-per-user view counting.

Revision ID: a9b1c2d3e4f5
Revises: d8e4f5a6b7c8
Create Date: 2026-10-14

The composite primary key (user_id, content_type, content_id) is the
deduplication guarantee: a second first-view by the same user for the same
policy or scheme fails at the database, so concurrent requests cannot
double-count a view.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: Union[str, None] = "a9b1c2d3e4f5"
down_revision: Union[str, None] = "d8e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_views",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("content_type", sa.String(length=16), primary_key=True),
        sa.Column("content_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "viewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_content_views_content",
        "content_views",
        ["content_type", "content_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_content_views_content", table_name="content_views")
    op.drop_table("content_views")

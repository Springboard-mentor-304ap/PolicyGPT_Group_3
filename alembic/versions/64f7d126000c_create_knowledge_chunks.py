"""create knowledge chunks

Revision ID: 64f7d126000c
Revises: e5f6a7b8c9d0
Create Date: 2026-10-08 01:45:19.042116

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "64f7d126000c"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_knowledge_chunks_source",
        "knowledge_chunks",
        ["source_type", "source_id"],
    )

    op.create_index(
        "ix_knowledge_chunks_source_type",
        "knowledge_chunks",
        ["source_type"],
    )

    # HNSW gives us efficient vector similarity search.
    op.execute(
        """
        CREATE INDEX ix_knowledge_chunks_embedding_hnsw
        ON knowledge_chunks
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_chunks_embedding_hnsw",
        table_name="knowledge_chunks",
    )
    op.drop_index(
        "ix_knowledge_chunks_source_type",
        table_name="knowledge_chunks",
    )
    op.drop_index(
        "ix_knowledge_chunks_source",
        table_name="knowledge_chunks",
    )
    op.drop_table("knowledge_chunks")
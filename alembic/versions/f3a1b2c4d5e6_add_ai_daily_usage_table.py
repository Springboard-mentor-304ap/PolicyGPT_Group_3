"""add ai_daily_usage quota table

Per-user, per-UTC-day counter of LLM calls, keyed by feature
(finder_extract / helpdesk). Backs the daily AI quota (429 when exceeded);
not a rate limiter.

Revision ID: f3a1b2c4d5e6
Revises: a9b1c2d3e4f5
Create Date: 2026-10-15
"""

from alembic import op
import sqlalchemy as sa


revision = "f3a1b2c4d5e6"
down_revision = "a9b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_daily_usage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            usage_date DATE NOT NULL,
            feature VARCHAR(50) NOT NULL,
            calls INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uix_ai_daily_usage_user_day_feature "
        "ON ai_daily_usage (user_id, usage_date, feature)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_daily_usage_usage_date "
        "ON ai_daily_usage (usage_date)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ai_daily_usage_usage_date")
    op.execute("DROP INDEX IF EXISTS uix_ai_daily_usage_user_day_feature")
    op.execute("DROP TABLE IF EXISTS ai_daily_usage")

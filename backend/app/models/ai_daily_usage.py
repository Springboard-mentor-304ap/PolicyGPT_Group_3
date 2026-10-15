from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class AIDailyUsage(Base):
    """One row per user, per feature, per UTC day: how many LLM calls they made.

    This is a usage counter, not a rate limiter: it caps the daily total of
    paid LLM calls per user and resets naturally at each UTC day. The
    increment is done atomically in SQL (upsert + RETURNING) so two
    concurrent requests cannot both slip past the limit.
    """

    __tablename__ = "ai_daily_usage"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    usage_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    feature: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    calls: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "usage_date",
            "feature",
            name="uix_ai_daily_usage_user_day_feature",
        ),
        Index("ix_ai_daily_usage_usage_date", "usage_date"),
    )

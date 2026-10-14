from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class ContentView(Base):
    """One row per (user, content) first view.

    Backs the one-view-per-user rule for policy and scheme view counts: the
    composite primary key makes a duplicate first-view attempt fail at the
    database, so concurrent requests cannot double-count, and the record
    survives restarts and multiple workers.

    `content_type` is a plain string ('policy' | 'scheme') so both tables
    share one small table instead of two near-identical ones.
    """

    __tablename__ = "content_views"

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(16),
        primary_key=True,
    )

    content_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_content_views_content",
            "content_type",
            "content_id",
        ),
    )

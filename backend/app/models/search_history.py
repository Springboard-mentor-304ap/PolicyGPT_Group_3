from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
    )

    query_text: Mapped[str | None] = mapped_column(
        String(255),
    )

    filters: Mapped[dict | None] = mapped_column(
        JSONB,
    )

    result_count: Mapped[int | None] = mapped_column(
        Integer,
    )

    searched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_search_history_user_id", "user_id"),
        Index("ix_search_history_searched_at", "searched_at"),
    )
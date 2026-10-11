from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class RefreshToken(Base):
    """One row per issued refresh token.

    Only the SHA-256 hash of the token's `jti` is stored, so a leaked
    database never contains a usable token (the same convention the password
    reset flow uses). A row is invalidated by stamping `revoked_at`; rotation
    revokes the presented row and issues a fresh one, and re-presenting a
    revoked row means the token leaked, so the caller revokes the whole chain.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    jti_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        # One hash per token: the lookup path for rotation and reuse detection.
        Index("ix_refresh_tokens_jti_hash", "jti_hash", unique=True),
    )

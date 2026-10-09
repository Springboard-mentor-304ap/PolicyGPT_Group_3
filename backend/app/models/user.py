from enum import Enum
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, String, Index, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.models.user_profile import UserProfile
    from backend.app.models.government_official_profile import GovernmentOfficialProfile


class UserRole(str, Enum):
    CITIZEN = "citizen"
    RESEARCHER = "researcher"
    ORGANIZATION = "organization"
    GOVERNMENT_OFFICIAL = "government_official"
    ADMINISTRATOR = "administrator"
    SUPER_ADMIN = "super_admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    phone: Mapped[str | None] = mapped_column(String(20))

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role"),
        nullable=False,
    )

    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=sa.false(),
    )

    email_verification_token: Mapped[str | None] = mapped_column(
        String(500),
    )

    # Single-use password reset token: stores `<sha256(jti)>:<unix-expiry>`.
    # The plaintext token (a JWT carrying the jti) is only ever sent by
    # e-mail; it is cleared as soon as it is used. Mirrors the
    # email_verification_token storage convention.
    password_reset_token: Mapped[str | None] = mapped_column(
        String(500),
    )

    profile: Mapped["UserProfile"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    government_official_profile: Mapped["GovernmentOfficialProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=sa.true()
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
        Index("ix_users_email", "email", unique=True),
    )


# E-mails are case-insensitive by definition, so the database enforces the
# same uniqueness the API applies through lowercase normalization.
Index(
    "uix_users_email_lower",
    func.lower(User.email),
    unique=True,
)

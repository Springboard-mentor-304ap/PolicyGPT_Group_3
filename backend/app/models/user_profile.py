from datetime import date, datetime
from enum import Enum
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, Enum as SQLEnum, Numeric, String, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.models.user import User

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

class MaritalStatus(str, Enum):
    SINGLE = "single"
    MARRIED = "married"
    OTHER = "other"

class SocialCategory(str, Enum):
    GENERAL = "general"
    OBC = "obc"
    SC = "sc"
    ST = "st"
    OTHER = "other"

class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user: Mapped["User"] = relationship(
        back_populates="profile",
    )

    date_of_birth: Mapped[date | None] = mapped_column(Date)

    gender: Mapped[Gender | None] = mapped_column(
        SQLEnum(Gender, name="gender"),
    )

    marital_status: Mapped[MaritalStatus | None] = mapped_column(
        SQLEnum(MaritalStatus, name="marital_status"),
    )

    religion: Mapped[str | None] = mapped_column(String(50))

    occupation: Mapped[str | None] = mapped_column(String(100))

    annual_income: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2)
    )

    social_category: Mapped[SocialCategory | None] = mapped_column(
        SQLEnum(SocialCategory, name="social_category")
    )

    disability_status: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=sa.false()
    )

    education: Mapped[str | None] = mapped_column(String(100))

    state: Mapped[str | None] = mapped_column(String(100))

    district: Mapped[str | None] = mapped_column(String(100))

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
        Index("ix_user_profiles_state", "state"),
        Index("ix_user_profiles_social_category", "social_category"),
        Index("ix_user_profiles_annual_income", "annual_income"),
    )
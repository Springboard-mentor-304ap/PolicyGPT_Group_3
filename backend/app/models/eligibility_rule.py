from datetime import date, datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import Index, ForeignKey, Enum as SQLEnum, String, DateTime, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base

class EligibilityParameter(str, Enum):
    AGE = "age"
    GENDER = "gender"
    INCOME = "income"
    OCCUPATION = "occupation"
    EDUCATION = "education"
    STATE = "state"
    DISTRICT = "district"
    SOCIAL_CATEGORY = "social_category"
    DISABILITY_STATUS = "disability_status"

class EligibilityOperator(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    IN = "in"
    NOT_IN = "not_in"

class EligibilityRule(Base):
    __tablename__ = "eligibility_rules"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    scheme_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schemes.id", ondelete="CASCADE"),
        nullable=False,
    )

    parameter: Mapped[EligibilityParameter] = mapped_column(
        SQLEnum(EligibilityParameter, name="eligibility_parameter"),
        nullable=False,
    )

    operator: Mapped[EligibilityOperator] = mapped_column(
        SQLEnum(EligibilityOperator, name="eligibility_operator"),
        nullable=False,
    )

    value: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
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
        Index("ix_eligibility_rules_scheme_id", "scheme_id"),
    )

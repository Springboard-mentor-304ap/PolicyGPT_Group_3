from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class SchemeCategory(str, Enum):
    SCHOLARSHIPS = "scholarships"
    FARMER_WELFARE = "farmer_welfare"
    HEALTHCARE = "healthcare"
    HOUSING = "housing"
    BUSINESS_SUPPORT = "business_support"
    WOMEN_EMPOWERMENT = "women_empowerment"
    SENIOR_CITIZEN_WELFARE = "senior_citizen_welfare"
    STUDENT_SCHEMES = "student_schemes"
    EMPLOYMENT_PROGRAMS = "employment_programs"
    SOCIAL_SECURITY = "social_security"


class SchemeStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    


class Scheme(Base):
    __tablename__ = "schemes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    policy_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    category: Mapped[SchemeCategory] = mapped_column(
        SQLEnum(SchemeCategory, name="scheme_category"),
        nullable=False,
    )

    benefits: Mapped[list[str] | None] = mapped_column(
        JSONB,
    )

    required_documents: Mapped[list[str] | None] = mapped_column(
        JSONB,
    )

    application_process: Mapped[str | None] = mapped_column(
        Text,
    )

    department: Mapped[str | None] = mapped_column(
        String(150),
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
    )

    status: Mapped[SchemeStatus] = mapped_column(
        SQLEnum(SchemeStatus, name="scheme_status"),
        nullable=False,
    )

    launch_date: Mapped[date | None] = mapped_column(
        Date,
    )

    deadline_date: Mapped[date | None] = mapped_column(
        Date,
    )

    document_url: Mapped[str | None] = mapped_column(
        String(500),
    )

    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    view_count: Mapped[int] = mapped_column(
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

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    __table_args__ = (
        Index("ix_schemes_policy_id", "policy_id"),
        Index("ix_schemes_category", "category"),
        Index("ix_schemes_status", "status"),
        Index("ix_schemes_state", "state"),
    )
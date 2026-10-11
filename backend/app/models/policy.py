from datetime import date, datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import Date, DateTime, Boolean, Enum as SQLEnum, func, ForeignKey, Integer, String, Text, Index, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base

class PolicyCategory(str, Enum):
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    AGRICULTURE = "agriculture"
    EMPLOYMENT = "employment"
    FINANCE = "finance"
    WOMEN_CHILD_WELFARE = "women_child_welfare"
    HOUSING = "housing"
    ENVIRONMENT = "environment"
    DIGITAL_GOVERNANCE = "digital_governance"
    INFRASTRUCTURE = "infrastructure"


class PolicyStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    required_documents: Mapped[list[str] | None] = mapped_column(
        JSONB,
    )

    category: Mapped[PolicyCategory] = mapped_column(
        SQLEnum(PolicyCategory, name="policy_category", values_callable=lambda enum: [member.value for member in enum],),
        nullable=False,
    )

    department: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    ministry: Mapped[str | None] = mapped_column(
        String(150),
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
    )

    status: Mapped[PolicyStatus] = mapped_column(
        SQLEnum(PolicyStatus, name="policy_status"),
        nullable=False,
    )

    document_url: Mapped[str | None] = mapped_column(
        String(500),
    )

    published_date: Mapped[date | None] = mapped_column(
        Date,
    )

    uploaded_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    approved_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id")
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
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
        Index("ix_policies_category", "category"),
        Index("ix_policies_state", "state"),
        Index("ix_policies_status", "status"),
        Index("ix_policies_department", "department"),
    )
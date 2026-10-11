from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base

class ApplicationStatus(str, Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ADDITIONAL_INFORMATION_REQUIRED = "additional_information_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    # Set by the applicant through the withdraw endpoint; terminal.
    WITHDRAWN = "withdrawn"

class Application(Base):
    __tablename__ = "applications"

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

    scheme_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schemes.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[ApplicationStatus] = mapped_column(
        SQLEnum(ApplicationStatus, name = "application_status"),
        nullable=False,
        server_default=ApplicationStatus.SUBMITTED.value,
    )

    remarks: Mapped[str | None] = mapped_column(
        Text,
    )

    approved_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
    )

    submitted_at: Mapped[datetime] = mapped_column(
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
        Index("ix_applications_user_id", "user_id"),
        Index("ix_applications_scheme_id", "scheme_id"),
        Index("ix_applications_status", "status"),
        # One application per user and scheme. Enforced by the database so
        # the check-then-insert in the service cannot race.
        Index(
            "uix_applications_user_scheme",
            "user_id",
            "scheme_id",
            unique=True,
        ),
    )
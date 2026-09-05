from enum import Enum
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.database import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.app.models.user import User


class RequestedRole(str, Enum):
    RESEARCHER = "researcher"
    ORGANIZATION = "organization"
    GOVERNMENT_OFFICIAL = "government_official"
    ADMINISTRATOR = "administrator"


class RequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class RoleRequest(Base):
    __tablename__ = "role_requests"

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

    requested_role: Mapped[RequestedRole] = mapped_column(
        SQLEnum(
            RequestedRole,
            name="requested_role",
            values_callable=lambda obj: [e.value for e in obj],
            create_type=False,
        ),
        nullable=False,
    )

    status: Mapped[RequestStatus] = mapped_column(
        SQLEnum(
            RequestStatus,
            name="request_status",
            values_callable=lambda obj: [e.value for e in obj],
            create_type=False,
        ),
        nullable=False,
        server_default=RequestStatus.PENDING.value,
    )

    # Role-specific form data stored as JSONB
    details: Mapped[dict | None] = mapped_column(JSONB)

    review_reason: Mapped[str | None] = mapped_column(Text)

    reviewer_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    user: Mapped["User"] = relationship(
        foreign_keys=[user_id],
        backref="role_requests",
    )

    reviewer: Mapped["User | None"] = relationship(
        foreign_keys=[reviewer_id],
    )

    __table_args__ = (
        Index("ix_role_requests_user_id", "user_id"),
        Index("ix_role_requests_status", "status"),
        Index("ix_role_requests_user_status", "user_id", "status"),
    )

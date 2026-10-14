from datetime import datetime
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.database import Base


class ReportType(str, Enum):
    POLICY = "policy"
    SCHEME = "scheme"
    USER_ACTIVITY = "user_activity"
    DEPARTMENT = "department"
    ANALYTICS = "analytics"


class ReportFormat(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )

    generated_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    report_type: Mapped[ReportType] = mapped_column(
        SQLEnum(ReportType, name="report_type"),
        nullable=False,
    )

    format: Mapped[ReportFormat] = mapped_column(
        SQLEnum(ReportFormat, name="report_format"),
        nullable=False,
    )

    filters_used: Mapped[dict | None] = mapped_column(
        JSONB,
    )

    file_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
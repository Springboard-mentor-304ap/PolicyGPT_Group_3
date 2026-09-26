from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.models.report import ReportFormat, ReportType


class ReportFilters(BaseModel):
    """Optional filters accepted while generating a report.

    Every field maps to a column that exists in the current models; which
    filters are accepted depends on the requested report type.
    """

    department: str | None = Field(default=None, max_length=150)
    ministry: str | None = Field(default=None, max_length=150)
    state: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=50)
    role: str | None = Field(default=None, max_length=50)
    date_from: date | None = None
    date_to: date | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "department",
        "ministry",
        "state",
        "category",
        "status",
        "role",
    )
    @classmethod
    def normalize_text_filter(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None


class ReportGenerateRequest(BaseModel):
    report_type: ReportType
    format: ReportFormat
    filters: ReportFilters | None = None

    model_config = ConfigDict(extra="forbid")


class ReportResponse(BaseModel):
    id: UUID
    generated_by: UUID
    report_type: ReportType
    format: ReportFormat
    filters_used: dict | None
    file_url: str
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportSummaryItem(BaseModel):
    label: str
    value: str


class ReportTable(BaseModel):
    title: str | None = None
    columns: list[str]
    rows: list[list[str | int | float | None]]


class ReportSection(BaseModel):
    title: str
    tables: list[ReportTable]


class ReportContent(BaseModel):
    """Internal contract shared between the report builders and the
    PDF / Excel generators.

    Values are kept as native types so the Excel export stays usable
    (numbers remain numbers) while the PDF export formats them as text.
    """

    title: str
    report_type: ReportType
    format: ReportFormat
    generated_at: datetime
    generated_by: str
    filters: dict[str, str]
    summary: list[ReportSummaryItem]
    sections: list[ReportSection]

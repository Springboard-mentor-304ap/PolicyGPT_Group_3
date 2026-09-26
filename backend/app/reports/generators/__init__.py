from datetime import datetime, timezone

from backend.app.models.report import ReportType


def format_timestamp(value: datetime) -> str:
    """Render a timestamp as a stable, timezone-explicit string."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def format_filters(filters: dict[str, str]) -> str:
    if not filters:
        return "None"

    return ", ".join(
        f"{key.replace('_', ' ').title()}: {value}"
        for key, value in filters.items()
    )


def report_type_label(report_type: ReportType) -> str:
    return report_type.value.replace("_", " ").title()

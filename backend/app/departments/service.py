from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.policy import Policy
from backend.app.models.scheme import Scheme


def _distinct_department_values(db: Session, column) -> list[str]:
    rows = db.execute(
        select(column).where(column.is_not(None)).distinct()
    ).scalars()

    return [
        value.strip()
        for value in rows
        if value and value.strip()
    ]


def list_departments(db: Session) -> list[str]:
    """Every department name currently used by a policy or a scheme.

    Values are merged case-insensitively so variant casing does not produce
    two visually identical options. The first spelling encountered is kept
    and stored values are never rewritten.
    """

    values = _distinct_department_values(db, Policy.department)
    values += _distinct_department_values(db, Scheme.department)

    seen: dict[str, str] = {}

    for value in values:
        seen.setdefault(value.casefold(), value)

    return sorted(seen.values(), key=str.casefold)

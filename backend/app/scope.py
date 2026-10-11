"""Canonical department/ministry scope rules for government officials.

Every module that narrows data for a government official (policies, schemes,
applications, search, analytics, reports) resolves the official's scope from
`GovernmentOfficialProfile.department` and then asks *this* module whether a
record belongs to it. Keeping the comparison in one place is what stops the
list views and the detail views from disagreeing.

The canonical rule:

* comparison is case-insensitive and ignores surrounding whitespace;
* a record is attributed to its **ministry first** and falls back to its
  **department** when it carries no ministry (policies, and the department
  report rows that group by those two columns);
* a scheme has no ministry of its own: it is in scope through its own
  department *or* through the ministry of its parent policy (the rule the
  scheme list, scheme detail, application review and analytics share).

Both the Python checks (`*_in_scope`) and the SQL filters (`*_scope_filter`)
implement the same rule, so a row that a list query returns is exactly a row
the detail view accepts.
"""

from sqlalchemy import func, or_, select

from backend.app.models.policy import Policy
from backend.app.models.scheme import Scheme


def normalize(value: str | None) -> str | None:
    """Trimmed, case-folded value; ``None`` when there is nothing to match."""
    if value is None:
        return None

    trimmed = value.strip()

    return trimmed.casefold() if trimmed else None


def record_owner(
    ministry: str | None,
    department: str | None,
) -> str | None:
    """Ministry first, department fallback (both trimmed)."""
    ministry = (ministry or "").strip()

    if ministry:
        return ministry

    department = (department or "").strip()

    return department or None


def is_in_scope(
    ministry: str | None,
    department: str | None,
    scope: str | None,
) -> bool:
    """Canonical check for a record that carries ministry + department."""
    owner = normalize(record_owner(ministry, department))
    target = normalize(scope)

    return owner is not None and target is not None and owner == target


def policy_in_scope(policy: Policy, scope: str | None) -> bool:
    return is_in_scope(policy.ministry, policy.department, scope)


def scheme_in_scope(
    scheme_department: str | None,
    policy_ministry: str | None,
    scope: str | None,
) -> bool:
    """Canonical check for a scheme (own department or parent ministry)."""
    target = normalize(scope)

    if target is None:
        return False

    department = normalize(scheme_department)

    if department is not None and department == target:
        return True

    ministry = normalize(policy_ministry)

    return ministry is not None and ministry == target


def _norm(column):
    """SQL counterpart of `normalize`: ``lower(trim(column))``.

    NULL stays NULL, so an empty scope value simply never matches — exactly
    like the Python checks returning False for it.
    """
    return func.lower(func.trim(column))


def _target(scope: str | None) -> str:
    normalized = normalize(scope)

    if normalized is None:
        raise ValueError("scope must be a non-empty string")

    return normalized


def normalized_match(column, scope: str | None):
    """Case-insensitive, trimmed equality between a column and the scope."""
    return _norm(column) == _target(scope)


def policy_scope_filter(scope: str | None, policy: type[Policy] | None = None):
    """SQL filter matching `policy_in_scope`: ministry, department fallback."""
    policy = policy or Policy
    target = _target(scope)
    owner = func.coalesce(
        func.nullif(_norm(policy.ministry), ""),
        _norm(policy.department),
    )

    return owner == target


def scheme_scope_filter(
    scope: str | None,
    scheme: type[Scheme] | None = None,
    policy: type[Policy] | None = None,
):
    """SQL filter matching `scheme_in_scope`: department or parent ministry."""
    scheme = scheme or Scheme
    policy = policy or Policy
    target = _target(scope)

    return or_(
        _norm(scheme.department) == target,
        scheme.policy_id.in_(
            select(policy.id).where(_norm(policy.ministry) == target)
        ),
    )

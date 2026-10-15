"""Scope / analytics / timestamp bugs (items 6, 7 and 8).

Item 8: one canonical scope rule (case-insensitive, trimmed, ministry first
with department fallback) — the list view and the detail view must agree,
also for mixed-case values.
Item 7: the scheme usage leaderboard is capped at the top 20 by views, in
the analytics endpoint and in the report that reuses it.
Item 6: archiving stores a timezone-aware UTC timestamp (no utcnow()).
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.app.analytics.service import get_scheme_statistics
from backend.app.models.government_official_profile import (
    GovernmentOfficialProfile,
)
from backend.app.models.policy import PolicyStatus
from backend.app.models.scheme import SchemeStatus
from backend.app.models.user import User, UserRole
from backend.app.reports.schemas import ReportFilters
from backend.app.reports.service import _build_analytics_report
from tests.api.conftest import _policy, _scheme


def _seed_official(seed, department: str) -> User:
    user = seed(
        User(
            id=uuid.uuid4(),
            email=f"official-{uuid.uuid4().hex[:8]}@example.gov",
            password_hash="x",
            full_name="Test Official",
            role=UserRole.GOVERNMENT_OFFICIAL,
            email_verified=True,
            is_active=True,
        )
    )
    seed(
        GovernmentOfficialProfile(
            user_id=user.id,
            department=department,
            designation="Officer",
            official_id=f"GOV-{uuid.uuid4().hex[:8].upper()}",
            state="Karnataka",
        )
    )
    return user


def _ids(response) -> set[str]:
    return {item["id"] for item in response.json()}


# ─── Item 8: policy list and detail agree ──────────────────────────────────
def test_policy_list_and_detail_scope_agree_for_mixed_case_values(
    api, seed, official,
):
    other = _seed_official(seed, "Finance")

    mixed = seed(
        _policy(
            title="Mixed Case Policy",
            ministry=" health ",  # trimmed + lower case
            status=PolicyStatus.APPROVED,
            uploaded_by=other.id,
        )
    )
    # No ministry at all: attributed through its department instead.
    department_only = seed(
        _policy(
            title="Department Only Policy",
            ministry=None,
            department="health",
            status=PolicyStatus.APPROVED,
            uploaded_by=other.id,
        )
    )
    outside = seed(
        _policy(
            title="Other Ministry Policy",
            ministry="Finance",
            department="Finance",
            status=PolicyStatus.APPROVED,
            uploaded_by=other.id,
        )
    )

    api.login(official)
    listed = _ids(api.client.get("/api/policies"))

    assert str(mixed.id) in listed
    assert str(department_only.id) in listed
    assert str(outside.id) not in listed

    # The detail view agrees with the list for every record: what is listed
    # is readable (200), what is not listed is rejected (403).
    for policy, should_be_visible in (
        (mixed, True),
        (department_only, True),
        (outside, False),
    ):
        detail = api.client.get(f"/api/policies/{policy.id}")
        assert (detail.status_code == 200) is should_be_visible, (
            policy.title,
            detail.status_code,
        )
        assert (str(policy.id) in listed) is should_be_visible


# ─── Item 8: scheme list and detail agree ──────────────────────────────────
def test_scheme_list_and_detail_scope_agree_for_mixed_case_values(
    api, seed, official,
):
    other = _seed_official(seed, "Finance")

    finance_policy = seed(
        _policy(
            title="Finance Policy",
            ministry="Finance",
            status=PolicyStatus.APPROVED,
            uploaded_by=other.id,
        )
    )
    health_policy = seed(
        _policy(
            title="Health Policy",
            ministry="health",  # lower case ministry
            status=PolicyStatus.APPROVED,
            uploaded_by=other.id,
        )
    )

    # In scope through its own (mixed-case) department.
    by_department = seed(
        _scheme(
            title="By Department",
            policy_id=finance_policy.id,
            created_by=other.id,
            department="HeAlTh",
            status=SchemeStatus.ACTIVE,
        )
    )
    # In scope through the ministry of its parent policy.
    by_ministry = seed(
        _scheme(
            title="By Ministry",
            policy_id=health_policy.id,
            created_by=other.id,
            department="Finance",
            status=SchemeStatus.ACTIVE,
        )
    )
    # Out of scope: neither branch matches.
    outside = seed(
        _scheme(
            title="Outside",
            policy_id=finance_policy.id,
            created_by=other.id,
            department="Finance",
            status=SchemeStatus.ACTIVE,
        )
    )

    api.login(official)
    listed = _ids(api.client.get("/api/schemes"))

    assert str(by_department.id) in listed
    assert str(by_ministry.id) in listed
    assert str(outside.id) not in listed

    for scheme, should_be_visible in (
        (by_department, True),
        (by_ministry, True),
        (outside, False),
    ):
        detail = api.client.get(f"/api/schemes/{scheme.id}")
        assert (detail.status_code == 200) is should_be_visible, (
            scheme.title,
            detail.status_code,
        )
        assert (str(scheme.id) in listed) is should_be_visible


# ─── Item 7: scheme usage capped at the top 20 by views ────────────────────
def test_scheme_usage_is_capped_to_top_20_in_endpoint_and_report(
    api, seed, session_factory, official, approved_policy,
):
    for index in range(25):
        seed(
            _scheme(
                title=f"Scheme {index:02d}",
                policy_id=approved_policy.id,
                created_by=official.id,
                status=SchemeStatus.ACTIVE,
                view_count=index,
            )
        )

    # Endpoint
    api.login(official)
    response = api.client.get("/api/analytics/schemes")
    assert response.status_code == 200
    usage = response.json()["scheme_usage"]
    assert len(usage) == 20
    views = [entry["view_count"] for entry in usage]
    assert views == sorted(views, reverse=True)
    assert views[0] == 24

    # Report (the same service, rendered into the "Scheme Usage" table)
    db = session_factory()

    try:
        _, sections = _build_analytics_report(
            db, ReportFilters(), "Health", official
        )
    finally:
        db.close()

    usage_table = next(
        table
        for section in sections
        if section.title == "Schemes"
        for table in section.tables
        if table.title and "Scheme Usage" in table.title
    )
    assert len(usage_table.rows) == 20

    # The service itself is capped as well.
    db = session_factory()

    try:
        stats = get_scheme_statistics(db, official)
    finally:
        db.close()

    assert len(stats["scheme_usage"]) == 20


# ─── Item 6: timezone-aware archive timestamps ─────────────────────────────
def test_archiving_stores_timezone_aware_utc_timestamps(
    api, monkeypatch, official, approved_policy, draft_scheme,
):
    recorded: list = []

    class RecordingDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = super().now(tz)
            recorded.append(value)
            return value

    from backend.app.policies import service as policies_service
    from backend.app.schemes import service as schemes_service

    monkeypatch.setattr(policies_service, "datetime", RecordingDateTime)
    monkeypatch.setattr(schemes_service, "datetime", RecordingDateTime)

    api.login(official)

    policy_response = api.client.post(
        f"/api/policies/{approved_policy.id}/archive"
    )
    assert policy_response.status_code == 200
    assert policy_response.json()["archived_at"] is not None

    scheme_response = api.client.post(
        f"/api/schemes/{draft_scheme.id}/archive"
    )
    assert scheme_response.status_code == 200
    assert scheme_response.json()["archived_at"] is not None

    # Bug: these used to be naive datetime.utcnow() values written into
    # timezone-aware columns.
    assert len(recorded) == 2
    for value in recorded:
        assert value.tzinfo is not None
        assert value.utcoffset().total_seconds() == 0

    # Nothing in the backend source uses utcnow() any more.
    backend_root = Path(__file__).resolve().parents[2] / "backend"
    offenders = [
        str(path)
        for path in backend_root.rglob("*.py")
        if "utcnow" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


# ─── Status-filter visibility rules are enforced server-side ──────────────
def _user_with_role(seed, role: UserRole) -> User:
    return seed(
        User(
            id=uuid.uuid4(),
            email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.gov",
            password_hash="x",
            full_name=f"Test {role.value}",
            role=role,
            email_verified=True,
            is_active=True,
        )
    )


def test_public_roles_list_only_approved_policies_and_active_schemes(
    api, seed, official,
):
    """Guests, citizens and organizations stay on public records.

    The list flags (`include_archived`, `by_me`) must not widen what these
    roles can see — the UI hides those controls from them, and the backend
    refuses the wider answer even when the flags are sent anyway. Staff
    roles keep both controls.
    """
    approved = seed(
        _policy(title="Approved", status=PolicyStatus.APPROVED,
                uploaded_by=official.id)
    )
    rejected = seed(
        _policy(title="Rejected", status=PolicyStatus.REJECTED,
                uploaded_by=official.id)
    )
    archived = seed(
        _policy(title="Archived", status=PolicyStatus.ARCHIVED,
                uploaded_by=official.id)
    )

    public_policy = seed(
        _policy(title="Public", status=PolicyStatus.APPROVED,
                uploaded_by=official.id)
    )
    active = seed(
        _scheme(policy_id=public_policy.id, created_by=official.id,
                status=SchemeStatus.ACTIVE)
    )
    draft = seed(
        _scheme(policy_id=public_policy.id, created_by=official.id,
                status=SchemeStatus.DRAFT)
    )
    scheme_archived = seed(
        _scheme(policy_id=public_policy.id, created_by=official.id,
                status=SchemeStatus.ARCHIVED)
    )

    expected_policies = {str(approved.id), str(public_policy.id)}
    expected_schemes = {str(active.id)}
    flags = {"include_archived": "true", "by_me": "true"}

    # Guest: no login yet — the widest flags still answer with public rows.
    assert _ids(api.client.get("/api/policies", params=flags)) == expected_policies
    assert _ids(api.client.get("/api/schemes", params=flags)) == expected_schemes

    for role in (UserRole.CITIZEN, UserRole.ORGANIZATION):
        api.login(_user_with_role(seed, role))
        assert (
            _ids(api.client.get("/api/policies", params=flags))
            == expected_policies
        )
        assert (
            _ids(api.client.get("/api/schemes", params=flags))
            == expected_schemes
        )

    # Government official (owner): the flags do widen their own records …
    api.login(official)
    official_policies = _ids(
        api.client.get("/api/policies", params={"include_archived": "true"})
    )
    assert str(rejected.id) in official_policies
    assert str(archived.id) in official_policies
    official_schemes = _ids(
        api.client.get("/api/schemes", params={"include_archived": "true"})
    )
    assert str(draft.id) in official_schemes
    assert str(scheme_archived.id) in official_schemes

    # … and so does an administrator.
    api.login(_user_with_role(seed, UserRole.ADMINISTRATOR))
    admin_schemes = _ids(
        api.client.get("/api/schemes", params={"include_archived": "true"})
    )
    assert str(scheme_archived.id) in admin_schemes

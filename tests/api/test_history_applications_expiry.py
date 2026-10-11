"""Items 6, 7 and 8: search history, application scheme context, expiry.

* GET/DELETE /search/history are scoped to the caller's own rows.
* The applicant's own application list carries scheme_title /
  scheme_department / scheme_deadline_date from a join, with the original
  fields untouched.
* `is_expired` is computed (never stored) and expired schemes are hidden from
  public listing/search by default but reachable with include_expired=true.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.auth.security import hash_password
from backend.app.models.application import Application, ApplicationStatus
from backend.app.models.government_official_profile import (
    GovernmentOfficialProfile,
)
from backend.app.models.policy import Policy, PolicyCategory, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeCategory, SchemeStatus
from backend.app.models.search_history import SearchHistory
from backend.app.models.user import User, UserRole

PASSWORD = "Sup3rSecret1"
TODAY = date.today()
BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _user(seed, role=UserRole.CITIZEN, password=None, **overrides):
    fields = dict(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:10]}@example.gov",
        password_hash=password or "x",
        full_name=f"User {role.value}",
        role=role,
        email_verified=True,
        is_active=True,
    )
    fields.update(overrides)
    return seed(User(**fields))


def _policy(seed, uploaded_by):
    return seed(
        Policy(
            id=uuid.uuid4(),
            title="Health Policy",
            description="Description",
            category=PolicyCategory.HEALTHCARE,
            department="Health",
            ministry="Health",
            status=PolicyStatus.APPROVED,
            uploaded_by=uploaded_by,
        )
    )


def _scheme(seed, policy_id, created_by, title, deadline_date, **overrides):
    fields = dict(
        id=uuid.uuid4(),
        policy_id=policy_id,
        title=title,
        description="Description",
        category=SchemeCategory.HEALTHCARE,
        department="Health",
        status=SchemeStatus.ACTIVE,
        created_by=created_by,
        deadline_date=deadline_date,
    )
    fields.update(overrides)
    return seed(Scheme(**fields))


# ─── Item 6: search history ─────────────────────────────────────────────────


def test_search_history_records_and_lists_the_callers_own_searches(
    real_auth, seed
):
    user = _user(seed, password=hash_password(PASSWORD))
    other = _user(seed)
    seed(
        SearchHistory(
            id=uuid.uuid4(),
            user_id=other.id,
            query_text="somebody else's search",
            searched_at=BASE_TIME,
        )
    )

    login = real_auth.post(
        "/api/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    search = real_auth.get("/api/search", params={"query": "health"}, headers=headers)
    assert search.status_code == 200, search.text

    history = real_auth.get("/api/search/history", headers=headers)
    assert history.status_code == 200, history.text

    rows = history.json()
    assert [row["query_text"] for row in rows] == ["health"]
    assert history.headers["X-Total-Count"] == "1"


def test_search_history_is_newest_first_and_paged(api, seed, session_factory):
    user = _user(seed)
    other = _user(seed)

    db = session_factory()
    try:
        for index in range(3):
            db.add(
                SearchHistory(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    query_text=f"mine {index}",
                    searched_at=BASE_TIME + timedelta(minutes=index),
                )
            )
        db.add(
            SearchHistory(
                id=uuid.uuid4(),
                user_id=other.id,
                query_text="theirs",
                searched_at=BASE_TIME + timedelta(hours=5),
            )
        )
        db.commit()
    finally:
        db.close()

    api.login(user)

    first = api.client.get("/api/search/history", params={"limit": 2})
    assert first.status_code == 200
    assert [row["query_text"] for row in first.json()] == ["mine 2", "mine 1"]
    assert first.headers["X-Total-Count"] == "3"

    second = api.client.get(
        "/api/search/history", params={"limit": 2, "offset": 2}
    )
    assert second.status_code == 200
    assert [row["query_text"] for row in second.json()] == ["mine 0"]


def test_delete_search_history_clears_only_the_callers_rows(
    api, seed, session_factory
):
    user = _user(seed)
    other = _user(seed)

    db = session_factory()
    try:
        db.add_all(
            [
                SearchHistory(
                    id=uuid.uuid4(), user_id=user.id, query_text="mine 1"
                ),
                SearchHistory(
                    id=uuid.uuid4(), user_id=user.id, query_text="mine 2"
                ),
                SearchHistory(
                    id=uuid.uuid4(), user_id=other.id, query_text="theirs"
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    api.login(user)
    cleared = api.client.delete("/api/search/history")
    assert cleared.status_code == 200
    assert cleared.json() == {"deleted": 2}

    remaining = (
        api.client.get("/api/search/history").json()
    )
    assert remaining == []

    db = session_factory()
    try:
        assert (
            db.query(SearchHistory)
            .filter(SearchHistory.user_id == other.id)
            .count()
            == 1
        )
    finally:
        db.close()


# ─── Item 7: application list joins scheme context ──────────────────────────


def test_my_applications_carry_scheme_context_and_keep_old_fields(api, seed):
    official = _user(seed, UserRole.GOVERNMENT_OFFICIAL)
    citizen = _user(seed)
    policy = _policy(seed, official.id)
    scheme = _scheme(
        seed,
        policy.id,
        official.id,
        title="Health Cover",
        deadline_date=date(2030, 1, 1),
    )

    application = seed(
        Application(
            id=uuid.uuid4(),
            user_id=citizen.id,
            scheme_id=scheme.id,
            status=ApplicationStatus.SUBMITTED,
        )
    )

    api.login(citizen)
    response = api.client.get("/api/applications")
    assert response.status_code == 200, response.text

    rows = response.json()
    assert len(rows) == 1
    row = rows[0]

    # The original payload is untouched …
    for field in (
        "id",
        "user_id",
        "scheme_id",
        "status",
        "remarks",
        "approved_by",
        "rejection_reason",
        "submitted_at",
        "updated_at",
    ):
        assert field in row, field
    assert row["id"] == str(application.id)
    assert row["status"] == "submitted"

    # … and the three new fields come from the join.
    assert row["scheme_title"] == "Health Cover"
    assert row["scheme_department"] == "Health"
    assert row["scheme_deadline_date"] == "2030-01-01"

    # The single-application endpoint keeps its original contract.
    detail = api.client.get(f"/api/applications/{application.id}")
    assert detail.status_code == 200
    assert "scheme_title" not in detail.json()
    assert "scheme_deadline_date" not in detail.json()


# ─── Item 8: computed expiry ────────────────────────────────────────────────


def test_expired_scheme_is_computed_and_hidden_for_public_users(api, seed):
    official = _user(seed, UserRole.GOVERNMENT_OFFICIAL)
    citizen = _user(seed)
    seed(
        GovernmentOfficialProfile(
            user_id=official.id,
            department="Health",
            designation="Director",
            official_id="GOV-5555",
            state="Karnataka",
        )
    )
    policy = _policy(seed, official.id)
    _scheme(
        seed,
        policy.id,
        official.id,
        title="Live Scheme",
        deadline_date=TODAY + timedelta(days=30),
    )
    expired = _scheme(
        seed,
        policy.id,
        official.id,
        title="Expired Scheme",
        deadline_date=TODAY - timedelta(days=1),
    )

    api.login(citizen)

    # Hidden by default …
    default = api.client.get("/api/schemes")
    assert default.status_code == 200
    titles = [row["title"] for row in default.json()]
    assert titles == ["Live Scheme"]
    assert default.json()[0]["is_expired"] is False
    assert default.headers["X-Total-Count"] == "1"

    # … but reachable on request, with the flag computed at response time.
    inclusive = api.client.get(
        "/api/schemes", params={"include_expired": "true"}
    )
    assert inclusive.status_code == 200
    by_title = {row["title"]: row["is_expired"] for row in inclusive.json()}
    assert by_title == {"Live Scheme": False, "Expired Scheme": True}
    assert inclusive.headers["X-Total-Count"] == "2"


def test_expired_scheme_status_is_not_changed_in_the_database(
    api, seed, session_factory
):
    official = _user(seed, UserRole.GOVERNMENT_OFFICIAL)
    policy = _policy(seed, official.id)
    expired = _scheme(
        seed,
        policy.id,
        official.id,
        title="Expired Scheme",
        deadline_date=TODAY - timedelta(days=1),
    )

    db = session_factory()
    try:
        stored = db.get(Scheme, expired.id)
        assert stored.status == SchemeStatus.ACTIVE
    finally:
        db.close()


def test_staff_still_see_expired_schemes_by_default(api, seed):
    """The expired filter targets public roles; staff manage those records."""
    official = _user(seed, UserRole.GOVERNMENT_OFFICIAL)
    seed(
        GovernmentOfficialProfile(
            user_id=official.id,
            department="Health",
            designation="Director",
            official_id="GOV-6666",
            state="Karnataka",
        )
    )
    policy = _policy(seed, official.id)
    _scheme(
        seed,
        policy.id,
        official.id,
        title="Live Scheme",
        deadline_date=TODAY + timedelta(days=30),
    )
    _scheme(
        seed,
        policy.id,
        official.id,
        title="Expired Scheme",
        deadline_date=TODAY - timedelta(days=1),
    )

    api.login(official)
    response = api.client.get("/api/schemes")
    assert response.status_code == 200
    assert {row["title"] for row in response.json()} == {
        "Live Scheme",
        "Expired Scheme",
    }


def test_search_hides_expired_schemes_for_public_callers(api, seed):
    official = _user(seed, UserRole.GOVERNMENT_OFFICIAL)
    policy = _policy(seed, official.id)
    _scheme(
        seed,
        policy.id,
        official.id,
        title="Live Scheme",
        deadline_date=TODAY + timedelta(days=30),
    )
    _scheme(
        seed,
        policy.id,
        official.id,
        title="Expired Scheme",
        deadline_date=TODAY - timedelta(days=1),
    )

    params = {"search_type": "scheme", "query": "Scheme"}

    # Guest caller: expired schemes stay out …
    hidden = api.client.get("/api/search", params=params)
    assert hidden.status_code == 200
    results = hidden.json()["results"]
    assert [row["title"] for row in results] == ["Live Scheme"]
    assert results[0]["is_expired"] is False

    # … and come back — flagged — when asked for.
    inclusive = api.client.get(
        "/api/search",
        params={**params, "include_expired": "true"},
    )
    assert inclusive.status_code == 200
    flagged = {
        row["title"]: row["is_expired"] for row in inclusive.json()["results"]
    }
    assert flagged == {"Live Scheme": False, "Expired Scheme": True}

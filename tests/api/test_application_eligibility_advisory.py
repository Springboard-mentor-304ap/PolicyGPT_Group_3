"""Advisory eligibility verdict on applications (Item 3).

Eligibility is ADVISORY, never enforced:

1. applying while not eligible still succeeds and stores the verdict;
2. the stored verdict comes from the server even if the client sends one;
3. a missing profile (or a scheme without rules) stores a NULL verdict and
   never blocks the application;
4. reviewing officials see the stored verdict;
5. the deadline boundary behaves the same after the UTC-date switch.
"""

import uuid
from datetime import date, timedelta

from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
    EligibilityRule,
)
from backend.app.models.scheme import SchemeStatus
from backend.app.models.user_profile import Gender, UserProfile
from tests.api.conftest import _scheme


def _seed_profile(session_factory, user_id, **overrides):
    fields = dict(
        user_id=user_id,
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
        annual_income=120000,
        occupation="farmer",
        education="secondary",
        state="Karnataka",
    )
    fields.update(overrides)
    profile = UserProfile(**fields)
    db = session_factory()
    try:
        db.add(profile)
        db.commit()
    finally:
        db.close()
    return profile


def _seed_rule(session_factory, scheme_id, parameter, operator, value):
    rule = EligibilityRule(
        scheme_id=scheme_id,
        parameter=parameter,
        operator=operator,
        value=value,
    )
    db = session_factory()
    try:
        db.add(rule)
        db.commit()
    finally:
        db.close()
    return rule


def _active_scheme(seed, official, approved_policy, **overrides):
    return seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
            **overrides,
        )
    )


# ─── 1 + 2: not eligible still applies; server computes the verdict ────────
def test_apply_while_not_eligible_succeeds_and_stores_server_verdict(
    api, seed, session_factory, citizen, official, approved_policy,
):
    scheme = _active_scheme(seed, official, approved_policy)
    # The citizen (born 1990) fails an "age >= 99" rule outright.
    _seed_rule(
        session_factory,
        scheme.id,
        EligibilityParameter.AGE,
        EligibilityOperator.GTE,
        "99",
    )
    _seed_profile(session_factory, citizen.id)

    api.login(citizen)
    response = api.client.post(
        "/api/applications",
        # The client lies about the verdict; it must be ignored.
        json={"scheme_id": str(scheme.id), "eligibility_verdict": "eligible"},
    )

    # Advisory: the application goes through regardless.
    assert response.status_code == 201
    body = response.json()
    # The stored verdict is the server's, not the client's.
    assert body["eligibility_verdict"] == "not_eligible"


# ─── 2b: eligible profile stores the positive verdict ─────────────────────
def test_apply_with_matching_profile_stores_eligible_verdict(
    api, seed, session_factory, citizen, official, approved_policy,
):
    scheme = _active_scheme(seed, official, approved_policy)
    _seed_rule(
        session_factory,
        scheme.id,
        EligibilityParameter.AGE,
        EligibilityOperator.GTE,
        "18",
    )
    _seed_profile(session_factory, citizen.id)

    api.login(citizen)
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(scheme.id)},
    )
    assert response.status_code == 201
    assert response.json()["eligibility_verdict"] == "eligible"


# ─── 3: missing profile / missing rules store NULL, never block ────────────
def test_missing_profile_stores_null_verdict_and_still_applies(
    api, seed, official, approved_policy,
):
    scheme = _active_scheme(seed, official, approved_policy)
    # No UserProfile seeded for this citizen.

    api.login(citizen := _fresh_citizen(seed))
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(scheme.id)},
    )
    assert response.status_code == 201
    assert response.json()["eligibility_verdict"] is None


def _fresh_citizen(seed):
    from backend.app.models.user import User, UserRole

    return seed(
        User(
            id=uuid.uuid4(),
            email=f"citizen-{uuid.uuid4().hex[:8]}@example.gov",
            password_hash="x",
            full_name="Profileless Citizen",
            role=UserRole.CITIZEN,
            email_verified=True,
            is_active=True,
        )
    )


def test_scheme_without_rules_stores_null_verdict_and_still_applies(
    api, seed, session_factory, citizen, official, approved_policy,
):
    scheme = _active_scheme(seed, official, approved_policy)
    _seed_profile(session_factory, citizen.id)  # profile present, no rules

    api.login(citizen)
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(scheme.id)},
    )
    assert response.status_code == 201
    assert response.json()["eligibility_verdict"] is None


# ─── 4: reviewing officials see the stored verdict ────────────────────────
def test_reviewers_see_the_stored_verdict(
    api, seed, session_factory, citizen, official, approved_policy,
):
    scheme = _active_scheme(seed, official, approved_policy)
    _seed_rule(
        session_factory,
        scheme.id,
        EligibilityParameter.AGE,
        EligibilityOperator.GTE,
        "99",
    )
    _seed_profile(session_factory, citizen.id)

    api.login(citizen)
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(scheme.id)},
    )
    assert response.status_code == 201
    application_id = response.json()["id"]

    # The official reviews: the verdict travels with both the list row and
    # the detail payload.
    api.login(official)

    listing = api.client.get("/api/applications/review")
    assert listing.status_code == 200
    row = next(
        item for item in listing.json() if item["id"] == application_id
    )
    assert row["eligibility_verdict"] == "not_eligible"

    detail = api.client.get(f"/api/applications/{application_id}")
    assert detail.status_code == 200
    assert detail.json()["eligibility_verdict"] == "not_eligible"


# ─── 5: deadline boundary unchanged after the UTC switch ──────────────────
def test_deadline_boundary_still_applies_in_utc(
    api, seed, citizen, official, approved_policy,
):
    today = date.today()

    expired = _active_scheme(
        seed, official, approved_policy,
        deadline_date=today - timedelta(days=1),
    )
    open_today = _active_scheme(
        seed, official, approved_policy,
        deadline_date=today,
    )

    api.login(citizen)

    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(expired.id)},
    )
    assert response.status_code == 400
    assert "deadline" in response.json()["detail"].lower()

    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(open_today.id)},
    )
    assert response.status_code == 201

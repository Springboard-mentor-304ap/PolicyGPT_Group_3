"""view_count bugs (item 1).

One user contributes at most one view per policy or scheme: repeat visits
and refreshes never double-count (deduplicated through the `content_views`
table), while a different user still adds their own view. Views are counted
with an atomic SQL increment and are never counted for the record's owner,
for administrators, or for requests that end in 403/404.
"""

import uuid

import pytest

from backend.app.models.government_official_profile import (
    GovernmentOfficialProfile,
)
from backend.app.models.policy import Policy
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.user import User, UserRole
from tests.api.conftest import _scheme


def _seed_user(seed, role, department=None):
    user = seed(
        User(
            id=uuid.uuid4(),
            email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.gov",
            password_hash="x",
            full_name="Test User",
            role=role,
            email_verified=True,
            is_active=True,
        )
    )

    if department is not None:
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


def _stored_view_count(session_factory, model, record_id) -> int:
    db = session_factory()
    try:
        return db.get(model, record_id).view_count
    finally:
        db.close()


@pytest.fixture()
def admin(seed):
    return _seed_user(seed, UserRole.ADMINISTRATOR)


@pytest.fixture()
def other_official(seed):
    # Different department, so this official is outside the "Health" scope.
    return _seed_user(seed, UserRole.GOVERNMENT_OFFICIAL, department="Finance")


@pytest.fixture()
def peer_official(seed):
    # Same department, but not the owner of any of the seeded records.
    return _seed_user(seed, UserRole.GOVERNMENT_OFFICIAL, department="Health")


def test_view_count_is_once_per_user_and_skips_owner_and_admin(
    api, seed, session_factory, citizen, official, admin,
    approved_policy, draft_policy,
):
    scheme = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
        )
    )

    second_citizen = _seed_user(seed, UserRole.CITIZEN)

    # ---- Policy ------------------------------------------------------------
    # One increment for the first visit ...
    api.login(citizen)
    response = api.client.get(f"/api/policies/{approved_policy.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 1

    # ... and repeat visits by the same user never double-count.
    response = api.client.get(f"/api/policies/{approved_policy.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 1
    response = api.client.get(f"/api/policies/{approved_policy.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 1

    # A different user still contributes their own view.
    api.login(second_citizen)
    response = api.client.get(f"/api/policies/{approved_policy.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 2

    # The owner's own visit is not counted ...
    api.login(official)
    response = api.client.get(f"/api/policies/{approved_policy.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 2

    # ... nor an administrator's.
    api.login(admin)
    response = api.client.get(f"/api/policies/{approved_policy.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 2

    # ---- Scheme ------------------------------------------------------------
    api.login(citizen)
    response = api.client.get(f"/api/schemes/{scheme.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 1

    response = api.client.get(f"/api/schemes/{scheme.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 1

    api.login(second_citizen)
    response = api.client.get(f"/api/schemes/{scheme.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 2

    api.login(official)  # creator
    response = api.client.get(f"/api/schemes/{scheme.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 2

    api.login(admin)
    response = api.client.get(f"/api/schemes/{scheme.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 2

    assert (
        _stored_view_count(session_factory, Policy, approved_policy.id) == 2
    )
    assert _stored_view_count(session_factory, Scheme, scheme.id) == 2


def test_failed_detail_requests_do_not_count_views(
    api, seed, session_factory, citizen, official, other_official,
    peer_official, approved_policy, draft_policy,
):
    draft_scheme = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.DRAFT,
        )
    )

    # 404: a citizen may not see a draft policy (nor a draft scheme), so the
    # request must not count a view.
    api.login(citizen)
    assert (
        api.client.get(f"/api/policies/{draft_policy.id}").status_code == 404
    )
    assert (
        api.client.get(f"/api/schemes/{draft_scheme.id}").status_code == 404
    )
    assert (
        _stored_view_count(session_factory, Policy, draft_policy.id) == 0
    )
    assert _stored_view_count(session_factory, Scheme, draft_scheme.id) == 0

    # 403: an official from another department is outside the scope, so the
    # request must not count a view either.
    api.login(other_official)
    assert (
        api.client.get(f"/api/policies/{approved_policy.id}").status_code
        == 403
    )
    assert (
        _stored_view_count(session_factory, Policy, approved_policy.id) == 0
    )

    # Normal path: an in-scope official who does not own the record is
    # counted.
    api.login(peer_official)
    response = api.client.get(f"/api/policies/{approved_policy.id}")
    assert response.status_code == 200
    assert response.json()["view_count"] == 1

"""End-to-end request tests for API bug fixes (profile, content, comparison).

One test per bug; every test drives a real HTTP request through the FastAPI
app (TestClient). The shared SQLite harness lives in conftest.py.
"""

from backend.app.models.policy import PolicyStatus
from backend.app.models.user_profile import UserProfile
from tests.api.conftest import _policy


# ─── Bug 1: PUT /profile/citizen reset disability_status to False ──────────

def test_put_profile_keeps_disability_status_when_field_omitted(api, seed, citizen):
    seed(
        UserProfile(
            user_id=citizen.id,
            disability_status=True,
        )
    )
    api.login(citizen)

    # Omitted field: must NOT overwrite the stored True (used to become False).
    response = api.client.put(
        "/api/profile/citizen",
        json={"occupation": "teacher"},
    )
    assert response.status_code == 200
    assert response.json()["disability_status"] is True

    # Normal path: an explicitly provided value is still applied.
    response = api.client.put(
        "/api/profile/citizen",
        json={"disability_status": False},
    )
    assert response.status_code == 200
    assert response.json()["disability_status"] is False

    # ...and persists across reads.
    response = api.client.get("/api/profile/citizen")
    assert response.status_code == 200
    assert response.json()["disability_status"] is False


# ─── Bug 2: create_scheme dropped required_documents ───────────────────────

def test_create_scheme_persists_required_documents(api, official, approved_policy):
    api.login(official)

    response = api.client.post(
        "/api/schemes",
        json={
            "policy_id": str(approved_policy.id),
            "title": "Health Cover Scheme",
            "description": "Free health cover",
            "required_documents": ["Aadhaar", "Income Certificate"],
            "category": "healthcare",
            "department": "Health",
        },
    )
    assert response.status_code == 201
    assert response.json()["required_documents"] == [
        "Aadhaar",
        "Income Certificate",
    ]

    # Normal path: omitted field stays null instead of erroring.
    response = api.client.post(
        "/api/schemes",
        json={
            "policy_id": str(approved_policy.id),
            "title": "Second Scheme",
            "description": "Another description",
            "category": "scholarships",
            "department": "Health",
        },
    )
    assert response.status_code == 201
    assert response.json()["required_documents"] is None


# ─── Bug 3: explicit nulls for non-nullable fields caused a 500 ────────────

def test_update_policy_rejects_null_for_non_nullable_fields(api, official, draft_policy):
    api.login(official)

    # Was an IntegrityError -> 500; now a 400 like the FAQ module.
    response = api.client.put(
        f"/api/policies/{draft_policy.id}",
        json={"title": None},
    )
    assert response.status_code == 400
    assert "title cannot be null" in response.json()["detail"]

    # Normal path: a real value is accepted.
    response = api.client.put(
        f"/api/policies/{draft_policy.id}",
        json={"title": "Renamed Policy"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed Policy"


def test_update_scheme_rejects_null_for_non_nullable_fields(api, official, draft_scheme):
    api.login(official)

    response = api.client.put(
        f"/api/schemes/{draft_scheme.id}",
        json={"category": None},
    )
    assert response.status_code == 400
    assert "category cannot be null" in response.json()["detail"]

    # Normal path: a real value is accepted.
    response = api.client.put(
        f"/api/schemes/{draft_scheme.id}",
        json={"title": "Renamed Scheme"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed Scheme"

    # Genuinely nullable column: explicit null is allowed and clears it.
    response = api.client.put(
        f"/api/schemes/{draft_scheme.id}",
        json={"department": None},
    )
    assert response.status_code == 200
    assert response.json()["department"] is None


# ─── Bug 4: annual_income of 0 serialised as null ──────────────────────────

def test_profile_income_zero_is_returned_as_zero(api, citizen):
    api.login(citizen)

    response = api.client.put(
        "/api/profile/citizen",
        json={"annual_income": 0},
    )
    assert response.status_code == 200
    assert response.json()["annual_income"] == 0

    response = api.client.get("/api/profile/citizen")
    assert response.status_code == 200
    assert response.json()["annual_income"] == 0

    # Normal path: a non-zero value round-trips too.
    response = api.client.put(
        "/api/profile/citizen",
        json={"annual_income": 150000.5},
    )
    assert response.status_code == 200
    assert response.json()["annual_income"] == 150000.5

    # Omitting the field keeps the stored 150000.5 rather than nulling it.
    response = api.client.put(
        "/api/profile/citizen",
        json={"occupation": "engineer"},
    )
    assert response.json()["annual_income"] == 150000.5


# ─── Bug 5: invalid gender/social_category raised ValueError -> 500 ────────

def test_put_profile_invalid_enum_values_return_422(api, citizen):
    api.login(citizen)

    response = api.client.put(
        "/api/profile/citizen",
        json={"gender": "not-a-gender"},
    )
    assert response.status_code == 422

    response = api.client.put(
        "/api/profile/citizen",
        json={"social_category": "not-a-category"},
    )
    assert response.status_code == 422

    # Normal path: valid values are accepted and echoed back.
    response = api.client.put(
        "/api/profile/citizen",
        json={"gender": "female", "social_category": "obc"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["gender"] == "female"
    assert body["social_category"] == "obc"


# ─── Bug 6: duplicate comparison ids returned 404 ──────────────────────────

def test_comparison_deduplicates_ids_and_returns_unique_items(api, citizen, seed, official):
    first = seed(
        _policy(
            uploaded_by=official.id,
            status=PolicyStatus.APPROVED,
            title="First Policy",
        )
    )
    second = seed(
        _policy(
            uploaded_by=official.id,
            status=PolicyStatus.APPROVED,
            title="Second Policy",
        )
    )
    api.login(citizen)

    # Same id twice used to 404 (length check compared against deduplicated
    # query rows). Now: dedupe first, return the unique items.
    response = api.client.post(
        "/api/comparison",
        json={"ids": [str(first.id), str(first.id)], "type": "policy"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(first.id)
    assert items[0]["title"] == "First Policy"

    # Normal path: distinct ids keep request order.
    response = api.client.post(
        "/api/comparison",
        json={
            "ids": [str(second.id), str(first.id)],
            "type": "policy",
        },
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [str(second.id), str(first.id)]

"""End-to-end request tests for the eligibility engine and rule-validation bugs.

One test per bug; every test drives a real HTTP request through the FastAPI
app (TestClient). The shared SQLite harness lives in conftest.py.
"""

from backend.app.models.eligibility_rule import (
    EligibilityOperator,
    EligibilityParameter,
    EligibilityRule,
)
from backend.app.models.scheme import SchemeStatus
from tests.api.conftest import _scheme


def _seed_rule(seed, scheme, parameter, operator, value):
    return seed(
        EligibilityRule(
            scheme_id=scheme.id,
            parameter=parameter,
            operator=operator,
            value=value,
        )
    )


# ─── Bug 1: IN/NOT_IN were defined but never validated for rules ──────────

def test_in_rule_creation_validates_the_list_format(api, official, draft_scheme):
    api.login(official)

    # Normal path: a well-formed list is accepted and stored.
    response = api.client.post(
        f"/api/schemes/{draft_scheme.id}/eligibility-rules",
        json={
            "parameter": "gender",
            "operator": "in",
            "value": "male, female",
        },
    )
    assert response.status_code == 201
    assert response.json()["value"] == "male, female"

    # Numeric list for a numeric parameter.
    response = api.client.post(
        f"/api/schemes/{draft_scheme.id}/eligibility-rules",
        json={
            "parameter": "age",
            "operator": "in",
            "value": "18,20,22",
        },
    )
    assert response.status_code == 201

    # Empty entries are rejected.
    for bad_value in ("male,,female", "male,", ",male"):
        response = api.client.post(
            f"/api/schemes/{draft_scheme.id}/eligibility-rules",
            json={
                "parameter": "gender",
                "operator": "in",
                "value": bad_value,
            },
        )
        assert response.status_code == 400

    # Every entry must be valid for the parameter.
    response = api.client.post(
        f"/api/schemes/{draft_scheme.id}/eligibility-rules",
        json={
            "parameter": "age",
            "operator": "in",
            "value": "18,abc",
        },
    )
    assert response.status_code == 400


# ─── Bug 2: no operator/parameter compatibility check ─────────────────────

def test_incompatible_operator_pairs_rejected_on_create_and_update(
    api, official, draft_scheme,
):
    api.login(official)

    # Categorical parameter + ordering operator.
    response = api.client.post(
        f"/api/schemes/{draft_scheme.id}/eligibility-rules",
        json={"parameter": "gender", "operator": "gte", "value": "18"},
    )
    assert response.status_code == 400
    assert "gender" in response.json()["detail"]

    # Disability status only accepts eq/neq, never list membership.
    response = api.client.post(
        f"/api/schemes/{draft_scheme.id}/eligibility-rules",
        json={
            "parameter": "disability_status",
            "operator": "in",
            "value": "true",
        },
    )
    assert response.status_code == 400

    # Numeric parameters do not take not_in.
    response = api.client.post(
        f"/api/schemes/{draft_scheme.id}/eligibility-rules",
        json={"parameter": "age", "operator": "not_in", "value": "17"},
    )
    assert response.status_code == 400

    # Normal path: compatible pairs are still accepted.
    response = api.client.post(
        f"/api/schemes/{draft_scheme.id}/eligibility-rules",
        json={"parameter": "age", "operator": "gte", "value": "18"},
    )
    assert response.status_code == 201

    response = api.client.post(
        f"/api/schemes/{draft_scheme.id}/eligibility-rules",
        json={"parameter": "gender", "operator": "eq", "value": "female"},
    )
    assert response.status_code == 201
    gender_rule_id = response.json()["id"]

    # Update: flipping only the operator to an incompatible one is rejected.
    response = api.client.put(
        f"/api/schemes/eligibility-rules/{gender_rule_id}",
        json={"operator": "gte"},
    )
    assert response.status_code == 400

    # A compatible operator change still works (the stored "female" is a
    # valid one-entry list for "in").
    response = api.client.put(
        f"/api/schemes/eligibility-rules/{gender_rule_id}",
        json={"operator": "in"},
    )
    assert response.status_code == 200

    response = api.client.put(
        f"/api/schemes/eligibility-rules/{gender_rule_id}",
        json={"value": "male,female"},
    )
    assert response.status_code == 200
    assert response.json()["value"] == "male,female"


# ─── Bug 3: disability_status defaulted to False, never "missing" ─────────

def test_disability_status_missing_versus_false(
    api, citizen, seed, official, approved_policy,
):
    scheme = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
        )
    )
    _seed_rule(
        seed,
        scheme,
        EligibilityParameter.DISABILITY_STATUS,
        EligibilityOperator.EQ,
        "true",
    )
    api.login(citizen)

    # A profile that never answered the question keeps it null in the API
    # (no fabricated False).
    response = api.client.put(
        "/api/profile/citizen",
        json={"state": "Karnataka"},
    )
    assert response.status_code == 200
    assert response.json()["disability_status"] is None

    # Missing information, not "not eligible".
    response = api.client.get(f"/api/eligibility/schemes/{scheme.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "more_information_required"
    assert "disability_status" in body["missing_information"]

    # An explicit False is a real answer: definitely not eligible.
    response = api.client.put(
        "/api/profile/citizen",
        json={"disability_status": False},
    )
    assert response.status_code == 200
    assert response.json()["disability_status"] is False

    response = api.client.get(f"/api/eligibility/schemes/{scheme.id}")
    assert response.status_code == 200
    assert response.json()["status"] == "not_eligible"

    # Normal path: an explicit True satisfies the rule.
    response = api.client.put(
        "/api/profile/citizen",
        json={"disability_status": True},
    )
    assert response.status_code == 200
    assert response.json()["disability_status"] is True

    response = api.client.get(f"/api/eligibility/schemes/{scheme.id}")
    assert response.status_code == 200
    assert response.json()["status"] == "eligible"


# ─── Bug 4: comparison printed raw "age gte 18" strings ───────────────────

def test_comparison_shows_human_readable_eligibility(
    api, citizen, seed, official, approved_policy,
):
    scheme = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
        )
    )
    for parameter, operator, value in (
        (EligibilityParameter.AGE, EligibilityOperator.GTE, "18"),
        (EligibilityParameter.INCOME, EligibilityOperator.LT, "300000"),
        (EligibilityParameter.GENDER, EligibilityOperator.EQ, "female"),
        (
            EligibilityParameter.STATE,
            EligibilityOperator.IN,
            "karnataka,maharashtra",
        ),
    ):
        _seed_rule(seed, scheme, parameter, operator, value)

    api.login(citizen)
    response = api.client.post(
        "/api/comparison",
        json={"ids": [str(scheme.id)], "type": "scheme"},
    )
    assert response.status_code == 200

    item = response.json()["items"][0]
    assert sorted(item["eligibility"]) == sorted(
        [
            "Age: 18 or above",
            "Income: below 300000",
            "Gender: female",
            "State: one of karnataka, maharashtra",
        ]
    )

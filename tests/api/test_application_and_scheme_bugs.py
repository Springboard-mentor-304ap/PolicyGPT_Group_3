"""End-to-end request tests for the application/scheme/policy bug batch.

One test per item; every test drives a real HTTP request through the
FastAPI app. Shared SQLite harness lives in conftest.py.
"""

import uuid
from datetime import date, timedelta

from backend.app.models.government_official_profile import (
    GovernmentOfficialProfile,
)
from backend.app.models.notification import Notification
from backend.app.models.policy import PolicyStatus
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.user import User, UserRole
from tests.api.conftest import _policy, _scheme


def _set_scheme_status(session_factory, scheme_id, new_status):
    db = session_factory()
    try:
        scheme = db.get(Scheme, scheme_id)
        scheme.status = new_status
        db.commit()
    finally:
        db.close()


def _set_official_department(session_factory, user_id, department):
    db = session_factory()
    try:
        profile = (
            db.query(GovernmentOfficialProfile)
            .filter(GovernmentOfficialProfile.user_id == user_id)
            .first()
        )
        profile.department = department
        db.commit()
    finally:
        db.close()


def _count_notifications(session_factory):
    db = session_factory()
    try:
        return db.query(Notification).count()
    finally:
        db.close()


# ─── Item 1: rejecting without remarks stored a null reason ────────────────

def test_rejecting_application_requires_remarks(api, seed, citizen, official, approved_policy):
    scheme = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
        )
    )
    api.login(citizen)
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(scheme.id)},
    )
    assert response.status_code == 201
    application_id = response.json()["id"]

    api.login(official)
    response = api.client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": "under_review"},
    )
    assert response.status_code == 200

    # Bug: this returned 200 and stored rejection_reason = None.
    response = api.client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": "rejected"},
    )
    assert response.status_code == 400
    assert "remarks" in response.json()["detail"].lower()

    # Whitespace-only remarks do not count either.
    response = api.client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": "rejected", "remarks": "   "},
    )
    assert response.status_code == 400

    # Normal path: real remarks are stored as the rejection reason.
    response = api.client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": "rejected", "remarks": "Missing documents"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "Missing documents"


# ─── Item 2: applications accepted after the scheme deadline ───────────────

def test_application_blocked_after_deadline(api, seed, citizen, official, approved_policy):
    today = date.today()
    expired = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
            deadline_date=today - timedelta(days=1),
        )
    )
    api.login(citizen)

    # Bug: an ACTIVE scheme with a past deadline still accepted applications.
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(expired.id)},
    )
    assert response.status_code == 400
    assert "deadline" in response.json()["detail"].lower()

    # Normal path: a future deadline still accepts applications.
    open_scheme = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
            deadline_date=today + timedelta(days=30),
        )
    )
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(open_scheme.id)},
    )
    assert response.status_code == 201

    # Boundary: a deadline of today is still an open window.
    today_scheme = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
            deadline_date=today,
        )
    )
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(today_scheme.id)},
    )
    assert response.status_code == 201


# ─── Item 3: rule changes blocked on ACTIVE/ARCHIVED schemes ────────────────

def test_rule_changes_blocked_on_active_schemes_and_allowed_on_pending(
    api, seed, session_factory, official, approved_policy, draft_policy,
):
    api.login(official)

    active = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
        )
    )
    rule_payload = {"parameter": "age", "operator": "gte", "value": "18"}

    # Bug: adding a rule to an ACTIVE scheme succeeded.
    response = api.client.post(
        f"/api/schemes/{active.id}/eligibility-rules",
        json=rule_payload,
    )
    assert response.status_code == 400
    assert "active or archived" in response.json()["detail"]

    # A scheme is created directly in PENDING_APPROVAL, so the creator must
    # be able to attach its eligibility rules while it awaits approval.
    pending = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.PENDING_APPROVAL,
        )
    )
    response = api.client.post(
        f"/api/schemes/{pending.id}/eligibility-rules",
        json=rule_payload,
    )
    assert response.status_code == 201

    # Create a rule while DRAFT, then flip the scheme to ACTIVE and try to
    # change and delete the rule (both used to succeed).
    draft = seed(
        _scheme(policy_id=draft_policy.id, created_by=official.id)
    )
    response = api.client.post(
        f"/api/schemes/{draft.id}/eligibility-rules",
        json=rule_payload,
    )
    assert response.status_code == 201
    rule_id = response.json()["id"]

    _set_scheme_status(session_factory, draft.id, SchemeStatus.ACTIVE)

    response = api.client.put(
        f"/api/schemes/eligibility-rules/{rule_id}",
        json={"value": "21"},
    )
    assert response.status_code == 400
    assert "active or archived" in response.json()["detail"]

    response = api.client.delete(
        f"/api/schemes/eligibility-rules/{rule_id}",
    )
    assert response.status_code == 400

    # Normal path: a DRAFT scheme's rules can still be edited and deleted.
    _set_scheme_status(session_factory, draft.id, SchemeStatus.DRAFT)

    response = api.client.put(
        f"/api/schemes/eligibility-rules/{rule_id}",
        json={"value": "21"},
    )
    assert response.status_code == 200
    assert response.json()["value"] == "21"

    response = api.client.delete(
        f"/api/schemes/eligibility-rules/{rule_id}",
    )
    assert response.status_code == 204


# ─── Item 4: deadline before launch date accepted ──────────────────────────

def test_scheme_dates_validated_on_create_and_update(
    api, official, approved_policy, draft_scheme,
):
    today = date.today()
    api.login(official)

    base_payload = {
        "policy_id": str(approved_policy.id),
        "title": "Dated Scheme",
        "description": "With awkward dates",
        "category": "healthcare",
        "department": "Health",
        "launch_date": today.isoformat(),
        "deadline_date": (today - timedelta(days=5)).isoformat(),
    }

    # Bug: create accepted a deadline before the launch date.
    response = api.client.post("/api/schemes", json=base_payload)
    assert response.status_code == 400
    assert "deadline" in response.json()["detail"].lower()

    # Normal path: a sane create succeeds.
    response = api.client.post(
        "/api/schemes",
        json={**base_payload, "deadline_date": (today + timedelta(days=30)).isoformat()},
    )
    assert response.status_code == 201

    # Update: move launch forward past the stored deadline — the check uses
    # the effective values (new launch, stored deadline).
    response = api.client.put(
        f"/api/schemes/{draft_scheme.id}",
        json={"launch_date": today.isoformat()},
    )
    assert response.status_code == 200

    response = api.client.put(
        f"/api/schemes/{draft_scheme.id}",
        json={"deadline_date": (today + timedelta(days=5)).isoformat()},
    )
    assert response.status_code == 200

    response = api.client.put(
        f"/api/schemes/{draft_scheme.id}",
        json={"launch_date": (today + timedelta(days=10)).isoformat()},
    )
    assert response.status_code == 400
    assert "deadline" in response.json()["detail"].lower()

    # Normal path: moving launch before the stored deadline still works.
    response = api.client.put(
        f"/api/schemes/{draft_scheme.id}",
        json={"launch_date": (today + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 200


# ─── Item 5: unarchive_policy skipped the department-scope check ───────────

def test_unarchive_policy_enforces_department_scope(api, seed, session_factory, official):
    policy = seed(
        _policy(
            uploaded_by=official.id,
            status=PolicyStatus.ARCHIVED,
            ministry="Health",
            department="Health",
        )
    )

    # The uploader's own scope no longer covers the policy.
    _set_official_department(session_factory, official.id, "Agriculture")
    api.login(official)

    # Bug: unarchive succeeded although archive_policy would 403 here.
    response = api.client.post(f"/api/policies/{policy.id}/unarchive")
    assert response.status_code == 403
    assert "department scope" in response.json()["detail"]

    # Normal path: an in-scope official may unarchive.
    _set_official_department(session_factory, official.id, "Health")
    response = api.client.post(f"/api/policies/{policy.id}/unarchive")
    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"


# ─── Item 6: role checked after loading (404 vs 403 leak) ──────────────────

def test_role_is_checked_before_loading_records(api, citizen, official, draft_policy):
    missing = uuid.uuid4()
    api.login(citizen)

    # Bug: every one of these answered 404 for a missing UUID (record load
    # ran before the role check), leaking existence to unauthorized callers.
    response = api.client.put(f"/api/policies/{missing}", json={"title": "x"})
    assert response.status_code == 403
    assert "Only government officials can update policies" in response.json()["detail"]

    response = api.client.post(f"/api/policies/{missing}/archive")
    assert response.status_code == 403
    assert "Only government officials can archive policies" in response.json()["detail"]

    response = api.client.post(f"/api/policies/{missing}/unarchive")
    assert response.status_code == 403
    assert "Only government officials can unarchive policies" in response.json()["detail"]

    response = api.client.post(f"/api/policies/{missing}/approve")
    assert response.status_code == 403
    assert "Only administrators can approve policies" in response.json()["detail"]

    response = api.client.put(f"/api/schemes/{missing}", json={"title": "x"})
    assert response.status_code == 403
    assert "Only government officials can manage schemes" in response.json()["detail"]

    response = api.client.post(f"/api/schemes/{missing}/archive")
    assert response.status_code == 403
    assert "Only government officials can manage schemes" in response.json()["detail"]

    response = api.client.post(
        f"/api/schemes/{missing}/eligibility-rules",
        json={"parameter": "age", "operator": "gte", "value": "18"},
    )
    assert response.status_code == 403
    assert "Only government officials can manage schemes" in response.json()["detail"]

    response = api.client.put(
        f"/api/schemes/eligibility-rules/{missing}",
        json={"value": "18"},
    )
    assert response.status_code == 403
    assert "Only government officials can manage schemes" in response.json()["detail"]

    response = api.client.delete(f"/api/schemes/eligibility-rules/{missing}")
    assert response.status_code == 403
    assert "Only government officials can manage schemes" in response.json()["detail"]

    # Normal path: the authorized owner still succeeds after the reorder.
    api.login(official)
    response = api.client.put(
        f"/api/policies/{draft_policy.id}",
        json={"title": "Renamed By Owner"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed By Owner"


# ─── Item 7: withdrawal of an in-progress application ──────────────────────

def test_withdraw_application(api, seed, session_factory, citizen, other_citizen, official, approved_policy):
    scheme = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
        )
    )
    api.login(citizen)
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(scheme.id)},
    )
    assert response.status_code == 201
    application_id = response.json()["id"]

    # Withdrawal notifies nobody.
    notifications_before = _count_notifications(session_factory)
    response = api.client.post(
        f"/api/applications/{application_id}/withdraw",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"
    assert _count_notifications(session_factory) == notifications_before

    # Conservative decision (flagged): the unique (user, scheme) row remains,
    # so a withdrawn applicant still cannot submit a fresh application.
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(scheme.id)},
    )
    assert response.status_code == 400
    assert "already applied" in response.json()["detail"]

    # Transition enforcement: once staff picks an application up, the
    # applicant can no longer withdraw it.
    scheme2 = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
        )
    )
    api.login(other_citizen)
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(scheme2.id)},
    )
    assert response.status_code == 201
    application2_id = response.json()["id"]

    api.login(official)
    response = api.client.patch(
        f"/api/applications/{application2_id}/status",
        json={"status": "under_review"},
    )
    assert response.status_code == 200

    api.login(other_citizen)
    response = api.client.post(
        f"/api/applications/{application2_id}/withdraw",
    )
    assert response.status_code == 400
    assert "Cannot change application status" in response.json()["detail"]

    # Ownership enforcement: someone else's application cannot be withdrawn.
    api.login(citizen)
    response = api.client.post(
        f"/api/applications/{application2_id}/withdraw",
    )
    assert response.status_code == 403

    # Decided applications stay final: a rejected applicant cannot reapply.
    api.login(official)
    response = api.client.patch(
        f"/api/applications/{application2_id}/status",
        json={"status": "rejected", "remarks": "Incomplete"},
    )
    assert response.status_code == 200

    api.login(other_citizen)
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(scheme2.id)},
    )
    assert response.status_code == 400


# ─── Administrators are excluded from the approval workflow ─────────────────

def test_administrators_cannot_review_update_or_view_applications(
    api, seed, citizen, official, approved_policy,
):
    """Application approvals are government-official work, end to end."""
    administrator = seed(
        User(
            id=uuid.uuid4(),
            email=f"admin-{uuid.uuid4().hex[:8]}@example.gov",
            password_hash="x",
            full_name="Test Admin",
            role=UserRole.ADMINISTRATOR,
            email_verified=True,
            is_active=True,
        )
    )
    scheme = seed(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            status=SchemeStatus.ACTIVE,
        )
    )

    api.login(citizen)
    response = api.client.post(
        "/api/applications",
        json={"scheme_id": str(scheme.id)},
    )
    assert response.status_code == 201
    application_id = response.json()["id"]

    api.login(administrator)

    # Review list: administrators must not see the approval queue.
    assert api.client.get("/api/applications/review").status_code == 403

    # Processing: administrators must not move an application along.
    response = api.client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": "under_review"},
    )
    assert response.status_code == 403

    # Seeing: administrators must not open the application either.
    assert (
        api.client.get(f"/api/applications/{application_id}").status_code
        == 403
    )

    # The in-scope government official keeps every capability.
    api.login(official)
    assert api.client.get("/api/applications/review").status_code == 200
    response = api.client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": "under_review"},
    )
    assert response.status_code == 200

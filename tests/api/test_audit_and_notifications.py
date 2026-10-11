"""Audit logging, workflow notification triggers, and GET /audit-logs.

Covers: one notification per trigger for the right recipients and never the
actor; audit rows written in the same transaction as the change and rolled
back with it; /audit-logs forbidden for non-admins; no secrets in `changes`.
"""

import uuid

import pytest

from backend.app.audit.service import client_ip, log_action
from backend.app.models.audit_log import AuditLog
from backend.app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationType,
)
from backend.app.models.policy import PolicyStatus
from backend.app.models.scheme import SchemeStatus
from backend.app.models.user import User, UserRole
from tests.api.conftest import _policy, _scheme


def _notes(db, user_id, ntype=None):
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if ntype is not None:
        query = query.filter(Notification.type == ntype)
    return query.all()


def _audits(db):
    return db.query(AuditLog).all()


@pytest.fixture()
def db_session(session_factory):
    db = session_factory()
    yield db
    db.close()


@pytest.fixture()
def admin(seed):
    return seed(
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


@pytest.fixture()
def pending_policy(seed, official):
    return seed(
        _policy(uploaded_by=official.id, status=PolicyStatus.PENDING_APPROVAL)
    )


@pytest.fixture()
def pending_scheme(seed, official, pending_policy):
    return seed(
        _scheme(
            policy_id=pending_policy.id,
            created_by=official.id,
            status=SchemeStatus.PENDING_APPROVAL,
        )
    )


# ─── Item 4: log_action stages without committing ───────────────────────────
def test_log_action_does_not_commit(db_session, session_factory, citizen):
    log_action(
        db=db_session,
        actor_id=citizen.id,
        action="test.action",
        target_table="users",
        target_id=citizen.id,
    )

    # Staged but not committed: another session cannot see it yet.
    other = session_factory()
    try:
        assert _audits(other) == []
    finally:
        other.close()

    db_session.commit()

    other = session_factory()
    try:
        rows = _audits(other)
        assert len(rows) == 1
        assert rows[0].action == "test.action"
    finally:
        other.close()


# ─── Item 3/4: policy rejection ─────────────────────────────────────────────
def test_reject_policy_notifies_uploader_and_writes_audit(
    db_session, citizen, admin, official, pending_policy,
):
    from backend.app.policies.service import reject_policy

    result = reject_policy(
        db=db_session,
        policy_id=pending_policy.id,
        rejection_reason="Needs a budget section",
        current_user=admin,
        request=None,
    )
    db_session.commit()

    # Exactly one notification, to the uploader (the official), never admin.
    uploader_notes = _notes(
        db_session, official.id, NotificationType.POLICY_REJECTED
    )
    assert len(uploader_notes) == 1
    assert "Needs a budget section" in uploader_notes[0].message
    assert uploader_notes[0].channel == NotificationChannel.IN_APP
    assert _notes(db_session, admin.id) == []

    rows = _audits(db_session)
    assert len(rows) == 1
    assert rows[0].action == "policy.reject"
    assert rows[0].actor_id == admin.id
    assert rows[0].target_id == pending_policy.id
    assert rows[0].target_table == "policies"
    assert rows[0].changes == {
        "status": {"old": "pending_approval", "new": "rejected"}
    }
    # changes carries status only — no password, token or hash material.
    assert set(rows[0].changes) == {"status"}
    assert result.status == PolicyStatus.REJECTED


# ─── Item 3: scheme approve/reject keep the public alert ────────────────────
def test_reject_scheme_notifies_creator_and_writes_audit(
    db_session, admin, official, pending_scheme,
):
    from backend.app.schemes.service import reject_scheme

    reject_scheme(
        db=db_session,
        scheme_id=pending_scheme.id,
        rejection_reason="Benefits list is incomplete",
        current_user=admin,
        request=None,
    )
    db_session.commit()

    creator_notes = _notes(
        db_session, official.id, NotificationType.SCHEME_REJECTED
    )
    assert len(creator_notes) == 1
    assert "Benefits list is incomplete" in creator_notes[0].message
    assert _notes(db_session, admin.id) == []

    rows = _audits(db_session)
    assert len(rows) == 1
    assert rows[0].action == "scheme.reject"
    assert rows[0].changes == {
        "status": {"old": "pending_approval", "new": "rejected"}
    }


def test_approve_scheme_notifies_creator_and_public_alert(
    db_session, session_factory, admin, official, pending_scheme, citizen,
):
    from backend.app.schemes.service import approve_scheme

    approve_scheme(
        db=db_session,
        scheme_id=pending_scheme.id,
        current_user=admin,
        request=None,
    )
    db_session.commit()

    # The creator gets SCHEME_APPROVED …
    assert len(
        _notes(db_session, official.id, NotificationType.SCHEME_APPROVED)
    ) == 1
    # … and the pre-existing public "Scheme Published" alert still fires.
    assert len(
        _notes(db_session, citizen.id, NotificationType.SCHEME_UPDATE)
    ) == 1
    # The actor is never notified about their own action.
    assert _notes(db_session, admin.id) == []

    rows = _audits(db_session)
    assert rows[0].action == "scheme.approve"
    assert rows[0].changes["status"]["new"] == "active"


# ─── Item 3: role request approve/reject ────────────────────────────────────
@pytest.fixture()
def pending_role_request(seed, citizen):
    from backend.app.models.role_request import (
        RequestedRole,
        RequestStatus,
        RoleRequest,
    )

    return seed(
        RoleRequest(
            user_id=citizen.id,
            requested_role=RequestedRole.GOVERNMENT_OFFICIAL,
            status=RequestStatus.PENDING,
            details={},
        )
    )


def test_role_request_rejection_notifies_requester_with_reason(
    api, db_session, admin, citizen, pending_role_request,
):
    api.login(admin)
    response = api.client.put(
        f"/api/role-requests/{pending_role_request.id}/reject",
        json={"review_reason": "Employment proof missing"},
    )
    assert response.status_code == 200

    notes = _notes(db_session, citizen.id, NotificationType.ROLE_REQUEST_UPDATE)
    assert len(notes) == 1
    assert "Employment proof missing" in notes[0].message
    assert _notes(db_session, admin.id) == []

    rows = _audits(db_session)
    assert rows[-1].action == "role_request.reject"
    assert rows[-1].changes["status"] == {"old": "pending", "new": "rejected"}
    # No secret material is recorded on the role change.
    assert "password" not in str(rows[-1].changes).lower()


# ─── Item 3: create_application notifies in-scope officials ─────────────────
def test_new_application_notifies_in_scope_officials(
    api, db_session, citizen, official, approved_policy,
):
    from tests.api.conftest import _scheme as make_scheme
    from backend.app.models.scheme import SchemeStatus as SS

    scheme = db_session.merge(
        make_scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            department="Health",
            status=SS.ACTIVE,
        )
    )
    db_session.commit()

    api.login(citizen)
    response = api.client.post(
        "/api/applications", json={"scheme_id": str(scheme.id)}
    )
    assert response.status_code == 201

    notes = _notes(db_session, official.id, NotificationType.NEW_APPLICATION)
    assert len(notes) == 1
    # The applicant is the actor here, so they must get nothing.
    assert _notes(db_session, citizen.id) == []


# ─── Item 5: GET /audit-logs ────────────────────────────────────────────────
def test_audit_logs_endpoint_forbidden_for_non_admins(api, citizen):
    api.login(citizen)
    assert api.client.get("/api/audit-logs").status_code == 403


def test_audit_logs_endpoint_filters_and_reports_total(
    api, db_session, admin, citizen,
):
    log_action(
        db=db_session,
        actor_id=admin.id,
        action="policy.approve",
        target_table="policies",
        target_id=uuid.uuid4(),
        changes={"status": {"old": "pending_approval", "new": "approved"}},
    )
    log_action(
        db=db_session,
        actor_id=citizen.id,
        action="role_request.submit",
        target_table="role_requests",
        target_id=uuid.uuid4(),
    )
    db_session.commit()

    api.login(admin)

    response = api.client.get("/api/audit-logs")
    assert response.status_code == 200
    assert int(response.headers["X-Total-Count"]) == 2
    assert len(response.json()) == 2

    # Newest first.
    body = response.json()
    assert body[0]["action"] == "role_request.submit"

    filtered = api.client.get(
        "/api/audit-logs", params={"action": "policy.approve"}
    )
    assert filtered.status_code == 200
    assert int(filtered.headers["X-Total-Count"]) == 1
    assert filtered.json()[0]["changes"]["status"]["new"] == "approved"

    by_actor = api.client.get(
        "/api/audit-logs", params={"actor_id": str(citizen.id)}
    )
    assert int(by_actor.headers["X-Total-Count"]) == 1

    empty = api.client.get(
        "/api/audit-logs", params={"target_table": "no_such_table"}
    )
    assert int(empty.headers["X-Total-Count"]) == 0
    assert empty.json() == []


# ─── Item 4: audit rows roll back with the failed change ────────────────────
def test_audit_row_rolls_back_when_commit_fails(
    db_session, session_factory, monkeypatch, admin, official, pending_policy,
):
    from backend.app.policies.service import reject_policy

    def boom(*args, **kwargs):
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(type(db_session), "commit", boom)

    with pytest.raises(RuntimeError):
        reject_policy(
            db=db_session,
            policy_id=pending_policy.id,
            rejection_reason="Fails on commit",
            current_user=admin,
            request=None,
        )

    monkeypatch.undo()
    db_session.rollback()

    other = session_factory()
    try:
        # Neither the change nor its audit row or notification survived.
        assert _audits(other) == []
        assert _notes(other, official.id) == []
        assert other.get(
            type(pending_policy), pending_policy.id
        ).status == PolicyStatus.PENDING_APPROVAL
    finally:
        other.close()


# ─── Item 3: feedback status change notifies the submitter ────────────────
@pytest.fixture()
def open_feedback(seed, citizen):
    from backend.app.models.feedback import Feedback, FeedbackStatus, FeedbackType

    return seed(
        Feedback(
            user_id=citizen.id,
            type=FeedbackType.ISSUE,
            subject="Cannot download report",
            message="The download button does nothing.",
            status=FeedbackStatus.OPEN,
        )
    )


def test_feedback_resolved_notifies_submitter_with_note(
    api, db_session, admin, citizen, open_feedback,
):
    api.login(admin)
    response = api.client.patch(
        f"/api/feedback/{open_feedback.id}",
        json={
            "status": "resolved",
            "resolution_note": "Cleared the stale file, please retry.",
        },
    )
    assert response.status_code == 200

    notes = _notes(db_session, citizen.id, NotificationType.FEEDBACK_UPDATE)
    assert len(notes) == 1
    # The resolution note travels with the notification …
    assert "Cleared the stale file" in notes[0].message
    assert notes[0].channel == NotificationChannel.IN_APP
    # … and the acting admin is never notified about their own action.
    assert _notes(db_session, admin.id) == []

    rows = _audits(db_session)
    assert rows[-1].action == "feedback.status_change"
    assert rows[-1].changes == {
        "status": {"old": "open", "new": "resolved"}
    }


def test_feedback_in_progress_notifies_without_note_requirement(
    api, db_session, admin, citizen, open_feedback,
):
    api.login(admin)
    response = api.client.patch(
        f"/api/feedback/{open_feedback.id}", json={"status": "in_progress"}
    )
    assert response.status_code == 200

    notes = _notes(db_session, citizen.id, NotificationType.FEEDBACK_UPDATE)
    assert len(notes) == 1
    assert "in progress" in notes[0].message


# ─── Item 3: admin alert is one query, not one per admin ────────────────────
def test_scheme_create_alerts_admins_with_a_single_query(
    db_session, session_factory, monkeypatch, official, approved_policy,
):
    """The recipient lookup must be one query, not a query per admin."""
    from sqlalchemy import event
    from backend.app.schemes.service import create_scheme
    from backend.app.schemes.schemas import SchemeCreate
    from backend.app.models.scheme import SchemeCategory

    # Two admins so "one per recipient" would show up as two lookups.
    for n in (1, 2):
        db_session.add(
            User(
                id=uuid.uuid4(),
                email=f"bulk-admin-{n}-{uuid.uuid4().hex[:6]}@example.gov",
                password_hash="x",
                full_name=f"Bulk Admin {n}",
                role=UserRole.ADMINISTRATOR,
                email_verified=True,
                is_active=True,
            )
        )
    db_session.commit()

    engine = session_factory.kw["bind"]
    selects: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        selects.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        create_scheme(
            db=db_session,
            scheme_data=SchemeCreate(
                policy_id=approved_policy.id,
                title="Bulk Alert Scheme",
                description="d",
                category=SchemeCategory.HEALTHCARE,
                department="Health",
            ),
            current_user=official,
            request=None,
        )
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    # Exactly one SELECT resolves every admin recipient. The role arrives as
    # a bound parameter, so match on the table only.
    admin_lookups = [
        s for s in selects
        if s.lstrip().upper().startswith("SELECT")
        and "users" in s.lower()
        and "role" in s.lower()
    ]
    assert len(admin_lookups) == 1, [" ".join(s.split()) for s in selects]

    admins = (
        db_session.query(User)
        .filter(User.role == UserRole.ADMINISTRATOR)
        .all()
    )
    for admin_user in admins:
        assert len(
            _notes(
                db_session, admin_user.id, NotificationType.APPROVAL_PENDING
            )
        ) == 1

    # The acting official created the scheme, so they are not notified.
    assert _notes(db_session, official.id) == []


# ─── Item 3: policy approval must not claim the policy was rejected ────────
def test_approve_policy_sends_no_rejection_notification(
    db_session, admin, official, pending_policy,
):
    """Regression: the shared audit helper used to send "Policy Rejected"
    for every policy action, so approving a policy told the uploader it had
    been rejected."""
    from backend.app.policies.service import approve_policy

    approve_policy(
        db=db_session,
        policy_id=pending_policy.id,
        current_user=admin,
        request=None,
    )
    db_session.commit()

    # The uploader hears nothing about a rejection, because there was none.
    assert _notes(db_session, official.id, NotificationType.POLICY_REJECTED) == []
    # And the acting admin is not notified about their own action.
    assert _notes(db_session, admin.id) == []

    # The audit row still records the real status transition.
    rows = _audits(db_session)
    assert rows[-1].action == "policy.approve"
    assert rows[-1].changes == {
        "status": {"old": "pending_approval", "new": "approved"}
    }


# ─── Item 3: create_application notifies in-scope officials ───────────────
def test_create_application_notifies_in_scope_officials(
    api, db_session, citizen, official, approved_policy,
):
    scheme = db_session.merge(
        _scheme(
            policy_id=approved_policy.id,
            created_by=official.id,
            department="Health",
            status=SchemeStatus.ACTIVE,
        )
    )
    db_session.commit()

    api.login(citizen)
    response = api.client.post(
        "/api/applications", json={"scheme_id": str(scheme.id)}
    )
    assert response.status_code == 201

    notes = _notes(db_session, official.id, NotificationType.NEW_APPLICATION)
    assert len(notes) == 1
    # The applicant is the actor, so they must not be notified.
    assert _notes(db_session, citizen.id) == []


def test_create_application_skips_notification_when_no_official_in_scope(
    api, db_session, citizen, official, approved_policy,
):
    """A scheme in a department with no official must not notify anyone."""
    # An approved policy filed under a ministry no official belongs to. The
    # scheme's own department must also be out of scope for every official.
    policy = db_session.merge(
        _policy(
            uploaded_by=official.id,
            status=PolicyStatus.APPROVED,
            department="Space Research",
            ministry="Space Research",
        )
    )
    scheme = db_session.merge(
        _scheme(
            policy_id=policy.id,
            created_by=official.id,
            department="Space Research",
            status=SchemeStatus.ACTIVE,
        )
    )
    db_session.commit()

    api.login(citizen)
    response = api.client.post(
        "/api/applications", json={"scheme_id": str(scheme.id)}
    )
    assert response.status_code == 201

    assert _notes(db_session, official.id, NotificationType.NEW_APPLICATION) == []
    assert (
        db_session.query(Notification)
        .filter(Notification.type == NotificationType.NEW_APPLICATION)
        .count()
        == 0
    )


# ─── Item 1: [DEV] secret logging is gated off in production ────────────────
def test_verification_code_not_printed_in_production(
    monkeypatch, capsys, citizen,
):
    from backend.app.auth import email_verification

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(
        email_verification, "send_email", lambda *a, **k: True
    )

    assert email_verification.send_verification_code(
        citizen.email, "123456"
    ) is True
    assert "123456" not in capsys.readouterr().out


def test_verification_code_printed_outside_production(
    monkeypatch, capsys, citizen,
):
    from backend.app.auth import email_verification

    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setattr(
        email_verification, "send_email", lambda *a, **k: True
    )

    email_verification.send_verification_code(citizen.email, "654321")
    assert "654321" in capsys.readouterr().out


def test_reset_token_not_printed_in_production(
    monkeypatch, capsys, citizen,
):
    from backend.app.auth import password_reset

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(
        password_reset, "send_email", lambda *a, **k: True
    )

    assert password_reset.send_password_reset_email(
        citizen.email, "reset-token-abc"
    ) is True
    assert "reset-token-abc" not in capsys.readouterr().out


# ─── Item 4: client_ip respects TRUSTED_PROXY ───────────────────────────────
class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, host, headers=None):
        self.client = _FakeClient(host)
        self.headers = headers or {}


def test_client_ip_ignores_forwarded_header_by_default(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY", raising=False)

    request = _FakeRequest(
        "10.0.0.5", headers={"x-forwarded-for": "1.2.3.4"}
    )
    assert client_ip(request) == "10.0.0.5"


def test_client_ip_honours_forwarded_header_when_trusted(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY", "true")

    request = _FakeRequest(
        "10.0.0.5", headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
    )
    assert client_ip(request) == "1.2.3.4"

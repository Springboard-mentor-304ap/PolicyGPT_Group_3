"""Reminder / notification analytics bugs (items 4 and 5).

Item 4: deadline reminders skip users who already applied, and the
"already reminded" / "already applied" lookups are one bulk query each.
Item 5: SMS rows are never actually sent, so they are excluded from the
notification analytics and from the report's notification section.
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import event

from backend.app.analytics.service import get_notification_statistics
from backend.app.models.application import Application, ApplicationStatus
from backend.app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationType,
)
from backend.app.models.scheme import SchemeStatus
from backend.app.models.user import User, UserRole
from backend.app.notifications.service import run_deadline_reminders
from backend.app.reports.service import _notification_section
from tests.api.conftest import _scheme


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


def _register_sqlite_timezone_function(session_factory):
    """SQLite has no timezone(); the report's dated series bucket with it.

    Registered on the pooled connection (StaticPool keeps a single one) the
    same way conftest.py registers gen_random_uuid().
    """
    engine = session_factory.kw["bind"]
    connection = engine.raw_connection()
    try:
        connection.create_function("timezone", 2, lambda zone, value: value)
    finally:
        connection.close()


def _deadline_row_count(db, user_id: uuid.UUID) -> int:
    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.type == NotificationType.DEADLINE_REMINDER,
        )
        .count()
    )


def _deadline_targets(db, user_id: uuid.UUID) -> set:
    rows = (
        db.query(Notification.related_entity_id)
        .filter(
            Notification.user_id == user_id,
            Notification.type == NotificationType.DEADLINE_REMINDER,
        )
        .all()
    )
    return {row[0] for row in rows}


# ─── Item 4: reminders skip applicants, bulk lookups ───────────────────────
def test_deadline_reminders_skip_applicants_and_query_in_bulk(
    session_factory, seed, citizen, other_citizen, approved_policy,
    monkeypatch,
):
    # No SMTP in tests: the reminder run only has to create the rows.
    from backend.app.notifications import service as notifications_service

    monkeypatch.setattr(
        notifications_service, "send_email", lambda **kwargs: None
    )

    closing_a = seed(
        _scheme(
            title="Closing Soon A",
            policy_id=approved_policy.id,
            created_by=approved_policy.uploaded_by,
            status=SchemeStatus.ACTIVE,
            deadline_date=date.today() + timedelta(days=3),
        )
    )
    closing_b = seed(
        _scheme(
            title="Closing Soon B",
            policy_id=approved_policy.id,
            created_by=approved_policy.uploaded_by,
            status=SchemeStatus.ACTIVE,
            deadline_date=date.today() + timedelta(days=5),
        )
    )

    # `citizen` already applied to scheme A and must not be reminded about it.
    seed(
        Application(
            user_id=citizen.id,
            scheme_id=closing_a.id,
            status=ApplicationStatus.SUBMITTED,
        )
    )

    engine = session_factory.kw["bind"]
    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)

    db = session_factory()

    try:
        summary = run_deadline_reminders(db, threshold_days=7)
    finally:
        # Stop recording before the assertions below run their own queries.
        event.remove(engine, "before_cursor_execute", _record)
        db.close()

    db = session_factory()

    try:
        # Bug: the applicant used to receive a reminder as well.
        assert _deadline_targets(db, citizen.id) == {closing_b.id}
        assert _deadline_targets(db, other_citizen.id) == {
            closing_a.id,
            closing_b.id,
        }

        # 3 notified pairs × (in_app, email, sms).
        assert (
            db.query(Notification)
            .filter(
                Notification.type == NotificationType.DEADLINE_REMINDER
            )
            .count()
            == 9
        )
    finally:
        db.close()

    assert summary["schemes_considered"] == 2
    assert summary["reminders_created"] == 3
    assert summary["reminders_skipped"] == 1

    # Bug: both lookups used to run once per user per scheme. They are now
    # exactly one query each for the whole run.
    application_selects = [
        statement
        for statement in statements
        if "from applications" in statement.lower()
    ]
    reminder_selects = [
        statement
        for statement in statements
        if statement.lower().startswith("select")
        and "from notifications" in statement.lower()
    ]
    assert len(application_selects) == 1
    assert len(reminder_selects) == 1

    # Normal path: a second run is idempotent — nothing new is created.
    db = session_factory()

    try:
        rerun = run_deadline_reminders(db, threshold_days=7)
        assert rerun["reminders_created"] == 0
        # All 4 (recipient, scheme) pairs are skipped: one applicant, three
        # already notified.
        assert rerun["reminders_skipped"] == 4
        assert (
            db.query(Notification)
            .filter(
                Notification.type == NotificationType.DEADLINE_REMINDER
            )
            .count()
            == 9
        )
    finally:
        db.close()


# ─── Item 5: SMS rows are excluded from analytics and reports ──────────────
def test_notification_analytics_and_report_exclude_sms(
    api, session_factory, seed, citizen, official, admin,
):
    _register_sqlite_timezone_function(session_factory)

    # 3 delivered channels (in_app, email, in_app) + 2 simulated SMS rows.
    seed(
        Notification(
            user_id=citizen.id,
            type=NotificationType.NEW_POLICY,
            channel=NotificationChannel.IN_APP,
            title="New policy",
            message="A policy was published",
        )
    )
    seed(
        Notification(
            user_id=citizen.id,
            type=NotificationType.APPLICATION_UPDATE,
            channel=NotificationChannel.EMAIL,
            title="Application update",
            message="Your application moved on",
        )
    )
    seed(
        Notification(
            user_id=official.id,
            type=NotificationType.APPLICATION_UPDATE,
            channel=NotificationChannel.IN_APP,
            title="Application update",
            message="Your application moved on",
        )
    )
    seed(
        Notification(
            user_id=citizen.id,
            type=NotificationType.DEADLINE_REMINDER,
            channel=NotificationChannel.SMS,
            title="Deadline reminder",
            message="Simulated SMS",
        )
    )
    seed(
        Notification(
            user_id=official.id,
            type=NotificationType.DEADLINE_REMINDER,
            channel=NotificationChannel.SMS,
            title="Deadline reminder",
            message="Simulated SMS",
        )
    )

    db = session_factory()

    try:
        stats = get_notification_statistics(db)
        section = _notification_section(db, stats)
    finally:
        db.close()

    # Bug: the SMS rows were counted as if they had been delivered.
    assert NotificationChannel.SMS.value not in stats["notifications_by_channel"]
    assert sum(stats["notifications_by_channel"].values()) == 3
    assert sum(stats["notifications_by_type"].values()) == 3
    assert sum(stats["notifications_by_read_status"].values()) == 3

    channel_table = next(
        table
        for table in section.tables
        if table.title == "Notifications by Channel"
    )
    assert {
        row[0]: row[1] for row in channel_table.rows
    } == {"email": 1, "in_app": 2}

    over_time = next(
        table
        for table in section.tables
        if table.title and "Over Time" in table.title
    )
    assert sum(row[1] for row in over_time.rows) == 3

    # Normal path: the analytics endpoint reports the same exclusions.
    api.login(admin)
    response = api.client.get("/api/analytics/notifications")
    assert response.status_code == 200
    payload = response.json()
    assert NotificationChannel.SMS.value not in payload[
        "notifications_by_channel"
    ]
    assert sum(payload["notifications_by_channel"].values()) == 3

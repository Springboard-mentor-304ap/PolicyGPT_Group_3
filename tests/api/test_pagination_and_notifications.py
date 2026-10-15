"""Items 4 and 5: paginated list endpoints and the notifications inbox.

Every paginated endpoint keeps its plain-array body, gains limit/offset
(default 100, ceiling 200) and reports the pre-paging total in
X-Total-Count; the notifications inbox additionally gains `unread_only` and
DELETE /notifications/{id}.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.models.application import Application, ApplicationStatus
from backend.app.models.faq import FAQ
from backend.app.models.government_official_profile import (
    GovernmentOfficialProfile,
)
from backend.app.models.feedback import Feedback, FeedbackStatus, FeedbackType
from backend.app.models.notification import (
    Notification,
    NotificationChannel,
    NotificationType,
)
from backend.app.models.policy import Policy, PolicyCategory, PolicyStatus
from backend.app.models.report import Report, ReportFormat, ReportType
from backend.app.models.scheme import Scheme, SchemeCategory, SchemeStatus
from backend.app.models.user import User, UserRole

BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _user(seed, role=UserRole.CITIZEN, **overrides):
    fields = dict(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:10]}@example.gov",
        password_hash="x",
        full_name=f"User {role.value}",
        role=role,
        email_verified=True,
        is_active=True,
    )
    fields.update(overrides)
    return seed(User(**fields))


def _stamp(index):
    """Distinct, deterministic timestamps so page boundaries are stable."""
    return BASE_TIME + timedelta(minutes=index)


def _assert_paged(client, url, params, expected_total):
    """Assert the full paging contract on one endpoint."""
    first = client.get(url, params={**params, "limit": 2, "offset": 0})
    assert first.status_code == 200, first.text
    rows = first.json()
    assert isinstance(rows, list), "the body must stay a plain array"
    assert len(rows) == min(2, expected_total)
    assert first.headers["X-Total-Count"] == str(expected_total)

    second = client.get(url, params={**params, "limit": 2, "offset": 2})
    assert second.status_code == 200, second.text
    assert second.headers["X-Total-Count"] == str(expected_total)

    if expected_total > 2:
        assert second.json(), "the second page must not be empty"
        assert not {row["id"] for row in rows} & {
            row["id"] for row in second.json()
        }

    # A page size above the ceiling is clamped, never a 422.
    clamped = client.get(url, params={**params, "limit": 5000})
    assert clamped.status_code == 200, clamped.text
    assert len(clamped.json()) == min(expected_total, 200)

    return rows


def _seed_policies(seed, count, uploaded_by):
    policies = []
    for index in range(count):
        policies.append(
            seed(
                Policy(
                    id=uuid.uuid4(),
                    title=f"Policy {index}",
                    description="Description",
                    category=PolicyCategory.HEALTHCARE,
                    department="Health",
                    ministry="Health",
                    status=PolicyStatus.APPROVED,
                    uploaded_by=uploaded_by,
                    created_at=_stamp(index),
                )
            )
        )
    return policies


def _seed_schemes(seed, count, policy_id, created_by):
    schemes = []
    for index in range(count):
        schemes.append(
            seed(
                Scheme(
                    id=uuid.uuid4(),
                    policy_id=policy_id,
                    title=f"Scheme {index}",
                    description="Description",
                    category=SchemeCategory.HEALTHCARE,
                    department="Health",
                    status=SchemeStatus.ACTIVE,
                    created_by=created_by,
                    created_at=_stamp(index),
                )
            )
        )
    return schemes


def test_policies_list_is_paginated(api, seed):
    official = _user(seed, UserRole.GOVERNMENT_OFFICIAL)
    citizen = _user(seed)
    _seed_policies(seed, 3, official.id)

    api.login(citizen)
    rows = _assert_paged(api.client, "/api/policies", {}, 3)
    # Existing ordering (newest first) is untouched.
    assert [row["title"] for row in rows] == ["Policy 2", "Policy 1"]


def test_schemes_list_is_paginated(api, seed):
    official = _user(seed, UserRole.GOVERNMENT_OFFICIAL)
    citizen = _user(seed)
    policy = _seed_policies(seed, 1, official.id)[0]
    _seed_schemes(seed, 3, policy.id, official.id)

    api.login(citizen)
    rows = _assert_paged(api.client, "/api/schemes", {}, 3)
    assert [row["title"] for row in rows] == ["Scheme 2", "Scheme 1"]


def test_faqs_list_is_paginated(api, seed):
    user = _user(seed)
    for index in range(3):
        seed(
            FAQ(
                id=uuid.uuid4(),
                question=f"Question {index}?",
                answer="Answer",
                category="General",
                is_active=True,
                created_by=user.id,
                created_at=_stamp(index),
            )
        )

    api.login(user)
    _assert_paged(api.client, "/api/faqs", {}, 3)


def test_reports_list_is_paginated(api, seed):
    administrator = _user(seed, UserRole.ADMINISTRATOR)
    for index in range(3):
        seed(
            Report(
                id=uuid.uuid4(),
                generated_by=administrator.id,
                report_type=ReportType.POLICY,
                format=ReportFormat.PDF,
                file_url=f"/tmp/report-{index}.pdf",
                generated_at=_stamp(index),
            )
        )

    api.login(administrator)
    _assert_paged(api.client, "/api/reports", {}, 3)


def test_feedback_list_is_paginated(api, seed):
    administrator = _user(seed, UserRole.ADMINISTRATOR)
    author = _user(seed)
    for index in range(3):
        seed(
            Feedback(
                id=uuid.uuid4(),
                user_id=author.id,
                type=FeedbackType.FEEDBACK,
                subject=f"Subject {index}",
                message="Message",
                status=FeedbackStatus.OPEN,
                created_at=_stamp(index),
            )
        )

    api.login(administrator)
    _assert_paged(api.client, "/api/feedback", {}, 3)


def test_my_feedback_list_is_paginated(api, seed):
    author = _user(seed)
    other = _user(seed)
    for index in range(3):
        seed(
            Feedback(
                id=uuid.uuid4(),
                user_id=author.id,
                type=FeedbackType.FEEDBACK,
                subject=f"Subject {index}",
                message="Message",
                status=FeedbackStatus.OPEN,
                created_at=_stamp(index),
            )
        )
    seed(
        Feedback(
            id=uuid.uuid4(),
            user_id=other.id,
            type=FeedbackType.FEEDBACK,
            subject="Somebody else's",
            message="Message",
            status=FeedbackStatus.OPEN,
            created_at=_stamp(9),
        )
    )

    api.login(author)

    # First page holds the two newest of the author's own entries …
    rows = _assert_paged(api.client, "/api/feedback/my", {}, 3)
    assert [row["subject"] for row in rows] == ["Subject 2", "Subject 1"]

    # … and nobody else's feedback is ever in this list.
    everything = api.client.get("/api/feedback/my", params={"limit": 500})
    assert {row["subject"] for row in everything.json()} == {
        "Subject 0",
        "Subject 1",
        "Subject 2",
    }


def test_applications_own_list_is_paginated(api, seed):
    official = _user(seed, UserRole.GOVERNMENT_OFFICIAL)
    citizen = _user(seed)
    policy = _seed_policies(seed, 1, official.id)[0]
    # One application per scheme: (user, scheme) is unique by design.
    schemes = _seed_schemes(seed, 3, policy.id, official.id)

    for index in range(3):
        seed(
            Application(
                id=uuid.uuid4(),
                user_id=citizen.id,
                scheme_id=schemes[index].id,
                status=ApplicationStatus.SUBMITTED,
                submitted_at=_stamp(index),
            )
        )

    api.login(citizen)
    _assert_paged(api.client, "/api/applications", {}, 3)


def test_applications_review_list_is_paginated(api, seed):
    official = _user(seed, UserRole.GOVERNMENT_OFFICIAL)
    # Review work requires the official profile (department scope).
    seed(
        GovernmentOfficialProfile(
            user_id=official.id,
            department="Health",
            designation="Director",
            official_id="GOV-1234",
            state="Karnataka",
        )
    )
    applicant = _user(seed)
    policy = _seed_policies(seed, 1, official.id)[0]
    schemes = _seed_schemes(seed, 3, policy.id, official.id)

    for index in range(3):
        seed(
            Application(
                id=uuid.uuid4(),
                user_id=applicant.id,
                scheme_id=schemes[index].id,
                status=ApplicationStatus.SUBMITTED,
                submitted_at=_stamp(index),
            )
        )

    # Review work is government-official only — administrators are
    # rejected with 403 (asserted in test_application_and_scheme_bugs).
    api.login(official)
    _assert_paged(api.client, "/api/applications/review", {}, 3)


def test_notifications_pagination_clamps_the_limit(api, seed, session_factory):
    user = _user(seed)

    db = session_factory()
    try:
        for index in range(205):
            db.add(
                Notification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    type=NotificationType.NEW_POLICY,
                    channel=NotificationChannel.IN_APP,
                    title=f"Notification {index}",
                    message="Message",
                    is_read=False,
                )
            )
        db.commit()
    finally:
        db.close()

    api.login(user)

    page = api.client.get("/api/notifications", params={"limit": 9999})
    assert page.status_code == 200, page.text
    assert len(page.json()) == 200
    assert page.headers["X-Total-Count"] == "205"

    tail = api.client.get(
        "/api/notifications", params={"limit": 9999, "offset": 200}
    )
    assert tail.status_code == 200
    assert len(tail.json()) == 5
    assert tail.headers["X-Total-Count"] == "205"


def test_notifications_unread_only_filter(api, seed, session_factory):
    user = _user(seed)
    other = _user(seed)

    db = session_factory()
    try:
        for index in range(3):
            db.add(
                Notification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    type=NotificationType.NEW_POLICY,
                    channel=NotificationChannel.IN_APP,
                    title=f"Unread {index}",
                    message="Message",
                    is_read=False,
                )
            )
        for index in range(2):
            db.add(
                Notification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    type=NotificationType.NEW_POLICY,
                    channel=NotificationChannel.IN_APP,
                    title=f"Read {index}",
                    message="Message",
                    is_read=True,
                )
            )
        # A delivery record: never part of the inbox, unread or not.
        db.add(
            Notification(
                id=uuid.uuid4(),
                user_id=user.id,
                type=NotificationType.APPLICATION_UPDATE,
                channel=NotificationChannel.EMAIL,
                title="Delivery record",
                message="Message",
                is_read=False,
            )
        )
        db.add(
            Notification(
                id=uuid.uuid4(),
                user_id=other.id,
                type=NotificationType.NEW_POLICY,
                channel=NotificationChannel.IN_APP,
                title="Somebody else's",
                message="Message",
                is_read=False,
            )
        )
        db.commit()
    finally:
        db.close()

    api.login(user)

    everything = api.client.get("/api/notifications")
    assert everything.status_code == 200
    assert everything.headers["X-Total-Count"] == "5"

    unread = api.client.get(
        "/api/notifications", params={"unread_only": "true"}
    )
    assert unread.status_code == 200
    titles = {row["title"] for row in unread.json()}
    assert titles == {"Unread 0", "Unread 1", "Unread 2"}
    assert unread.headers["X-Total-Count"] == "3"


def test_delete_notification_is_scoped_to_owner_and_in_app(
    api, seed, session_factory
):
    user = _user(seed)
    other = _user(seed)

    db = session_factory()
    try:
        mine = Notification(
            id=uuid.uuid4(),
            user_id=user.id,
            type=NotificationType.NEW_POLICY,
            channel=NotificationChannel.IN_APP,
            title="Mine",
            message="Message",
            is_read=False,
        )
        my_delivery = Notification(
            id=uuid.uuid4(),
            user_id=user.id,
            type=NotificationType.APPLICATION_UPDATE,
            channel=NotificationChannel.EMAIL,
            title="My delivery record",
            message="Message",
            is_read=False,
        )
        theirs = Notification(
            id=uuid.uuid4(),
            user_id=other.id,
            type=NotificationType.NEW_POLICY,
            channel=NotificationChannel.IN_APP,
            title="Theirs",
            message="Message",
            is_read=False,
        )
        db.add_all([mine, my_delivery, theirs])
        db.commit()
        mine_id, delivery_id, theirs_id = mine.id, my_delivery.id, theirs.id
    finally:
        db.close()

    api.login(user)

    # Delivery records are not inbox entries.
    delivery = api.client.delete(f"/api/notifications/{delivery_id}")
    assert delivery.status_code == 404

    # Somebody else's notification does not exist for this caller.
    foreign = api.client.delete(f"/api/notifications/{theirs_id}")
    assert foreign.status_code == 404

    deleted = api.client.delete(f"/api/notifications/{mine_id}")
    assert deleted.status_code == 204

    db = session_factory()
    try:
        remaining = {
            row.title
            for row in db.query(Notification).filter(
                Notification.user_id.in_([user.id, other.id])
            )
        }
        assert remaining == {"My delivery record", "Theirs"}
    finally:
        db.close()

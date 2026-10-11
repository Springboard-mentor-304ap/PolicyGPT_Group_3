"""Item 1: /admin/users management.

One test per rule: the permission matrix (every actor role x every target
role, plus self and super-admin targets), the never-leaking response schema,
escaped search, filters + X-Total-Count, the audit trail, the "notifies
nobody" rule, and a real token dying the moment its owner is deactivated.
"""

import uuid

import pytest

from backend.app.auth.security import hash_password
from backend.app.models.audit_log import AuditLog
from backend.app.models.government_official_profile import GovernmentOfficialProfile
from backend.app.models.notification import Notification
from backend.app.models.refresh_token import RefreshToken
from backend.app.models.user import User, UserRole

ALL_ROLES = [
    UserRole.CITIZEN,
    UserRole.RESEARCHER,
    UserRole.ORGANIZATION,
    UserRole.GOVERNMENT_OFFICIAL,
    UserRole.ADMINISTRATOR,
    UserRole.SUPER_ADMIN,
]

MANAGEABLE_TARGET_ROLES = [
    UserRole.CITIZEN,
    UserRole.RESEARCHER,
    UserRole.ORGANIZATION,
    UserRole.GOVERNMENT_OFFICIAL,
]

# Exactly what GET /admin/users may serialise — anything else (password_hash,
# verification/reset tokens) leaking into the payload fails the test below.
SAFE_FIELDS = {
    "id",
    "full_name",
    "email",
    "phone",
    "role",
    "is_active",
    "email_verified",
    "created_at",
    "updated_at",
}


def _user(role, **overrides):
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
    return User(**fields)


def _expected_status(actor_role, target_role):
    """The documented permission matrix for a per-user admin action."""
    if actor_role not in (UserRole.ADMINISTRATOR, UserRole.SUPER_ADMIN):
        return 403

    if target_role == UserRole.SUPER_ADMIN:
        return 403

    if actor_role == UserRole.ADMINISTRATOR and target_role == UserRole.ADMINISTRATOR:
        return 403

    return 200


@pytest.fixture()
def actors(seed):
    """One actor of every role."""
    return {role: seed(_user(role)) for role in ALL_ROLES}


@pytest.fixture()
def targets(seed):
    """One target of every role, distinct from the actors."""
    return {role: seed(_user(role)) for role in ALL_ROLES}


def test_admin_users_permission_matrix(api, actors, targets):
    for actor_role, actor in actors.items():
        for target_role, target in targets.items():
            api.login(actor)

            read = api.client.get(f"/api/admin/users/{target.id}")
            assert read.status_code == _expected_status(actor_role, target_role), (
                actor_role,
                target_role,
                read.text,
            )

            deactivate = api.client.post(
                f"/api/admin/users/{target.id}/deactivate"
            )
            assert deactivate.status_code == _expected_status(
                actor_role, target_role
            ), (actor_role, target_role, deactivate.text)


def test_admin_users_nobody_can_act_on_self(api, actors):
    """Self-deactivation would lock an administrator out of the platform."""
    for actor_role, actor in actors.items():
        api.login(actor)

        response = api.client.post(f"/api/admin/users/{actor.id}/deactivate")
        assert response.status_code == 403, (actor_role, response.text)

        read = api.client.get(f"/api/admin/users/{actor.id}")
        assert read.status_code == 403, (actor_role, read.text)


def test_admin_users_unknown_target_is_404(api, actors):
    api.login(actors[UserRole.ADMINISTRATOR])

    response = api.client.post("/api/admin/users/%s/deactivate" % uuid.uuid4())
    assert response.status_code == 404


def test_admin_users_response_never_leaks_secrets(api, seed, actors):
    administrator = actors[UserRole.ADMINISTRATOR]
    api.login(administrator)

    for path in ("/api/admin/users", f"/api/admin/users/{actors[UserRole.CITIZEN].id}"):
        response = api.client.get(path)
        assert response.status_code == 200

        rows = response.json()
        rows = rows if isinstance(rows, list) else [rows]

        for row in rows:
            assert set(row.keys()) == SAFE_FIELDS, set(row.keys())


def test_admin_users_filters_search_escaping_and_total_header(api, seed):
    administrator = seed(_user(UserRole.ADMINISTRATOR))
    seed(_user(UserRole.CITIZEN, full_name="100% Bonus Fund"))
    seed(_user(UserRole.CITIZEN, full_name="100 Percent Fund"))
    seed(_user(UserRole.CITIZEN, full_name="Grant_A Holder"))
    seed(_user(UserRole.CITIZEN, full_name="Grant Area"))
    inactive = seed(_user(UserRole.RESEARCHER, is_active=False))

    api.login(administrator)

    by_role = api.client.get("/api/admin/users", params={"role": "citizen"})
    assert by_role.status_code == 200
    assert {row["role"] for row in by_role.json()} == {"citizen"}

    inactive_rows = api.client.get(
        "/api/admin/users", params={"is_active": "false"}
    )
    assert [row["id"] for row in inactive_rows.json()] == [str(inactive.id)]

    # "%" is escaped, so it matches the literal name and nothing else.
    percent = api.client.get("/api/admin/users", params={"search": "100%"})
    assert [row["full_name"] for row in percent.json()] == ["100% Bonus Fund"]

    # Same for "_", which would otherwise match any single character.
    underscore = api.client.get("/api/admin/users", params={"search": "Grant_A"})
    assert [row["full_name"] for row in underscore.json()] == ["Grant_A Holder"]

    # The header carries the filtered total, independent of the page size.
    paged = api.client.get(
        "/api/admin/users", params={"role": "citizen", "limit": 1}
    )
    assert paged.status_code == 200
    assert len(paged.json()) == 1
    assert paged.headers["X-Total-Count"] == "4"


def test_admin_deactivate_writes_audit_row_and_notifies_nobody(
    api, seed, session_factory
):
    administrator = seed(_user(UserRole.ADMINISTRATOR))
    target = seed(_user(UserRole.CITIZEN))

    api.login(administrator)
    deactivate = api.client.post(f"/api/admin/users/{target.id}/deactivate")
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    reactivate = api.client.post(f"/api/admin/users/{target.id}/reactivate")
    assert reactivate.status_code == 200
    assert reactivate.json()["is_active"] is True

    db = session_factory()
    try:
        rows = (
            db.query(AuditLog)
            .filter(AuditLog.target_id == target.id)
            .all()
        )
        assert {row.action for row in rows} == {
            "admin.user_deactivate",
            "admin.user_reactivate",
        }
        assert {row.actor_id for row in rows} == {administrator.id}
        assert {row.target_table for row in rows} == {"users"}

        # Deactivation notifies nobody.
        assert (
            db.query(Notification)
            .filter(Notification.user_id == target.id)
            .count()
            == 0
        )
    finally:
        db.close()


def test_admin_revoke_role_demotes_official_and_deletes_profile(
    api, seed, session_factory
):
    administrator = seed(_user(UserRole.ADMINISTRATOR))
    official = seed(_user(UserRole.GOVERNMENT_OFFICIAL))
    seed(
        GovernmentOfficialProfile(
            user_id=official.id,
            department="Health",
            designation="Director",
            official_id="GOV-9911",
            state="Karnataka",
        )
    )

    api.login(administrator)
    response = api.client.post(f"/api/admin/users/{official.id}/revoke-role")

    assert response.status_code == 200
    assert response.json()["role"] == "citizen"

    db = session_factory()
    try:
        assert db.get(User, official.id).role == UserRole.CITIZEN
        assert (
            db.query(GovernmentOfficialProfile)
            .filter(GovernmentOfficialProfile.user_id == official.id)
            .count()
            == 0
        )
        assert (
            db.query(AuditLog)
            .filter(
                AuditLog.target_id == official.id,
                AuditLog.action == "admin.user_revoke_role",
            )
            .count()
            == 1
        )
    finally:
        db.close()


def test_deactivated_user_token_stops_working_immediately(
    real_auth, seed, session_factory
):
    """Real JWTs end to end: login, deactivate, watch both tokens die."""
    password = "Sup3rSecret1"
    administrator = seed(
        _user(UserRole.ADMINISTRATOR, password_hash=hash_password(password))
    )
    target = seed(_user(UserRole.CITIZEN, password_hash=hash_password(password)))

    target_login = real_auth.post(
        "/api/auth/login",
        json={"email": target.email, "password": password},
    )
    assert target_login.status_code == 200
    target_tokens = target_login.json()

    admin_login = real_auth.post(
        "/api/auth/login",
        json={"email": administrator.email, "password": password},
    )
    assert admin_login.status_code == 200
    admin_headers = {
        "Authorization": f"Bearer {admin_login.json()['access_token']}"
    }
    target_headers = {
        "Authorization": f"Bearer {target_tokens['access_token']}"
    }

    before = real_auth.get("/api/auth/me", headers=target_headers)
    assert before.status_code == 200

    deactivate = real_auth.post(
        f"/api/admin/users/{target.id}/deactivate", headers=admin_headers
    )
    assert deactivate.status_code == 200

    # get_current_user checks is_active, so the very next call fails.
    after = real_auth.get("/api/auth/me", headers=target_headers)
    assert after.status_code == 403

    # And the refresh token cannot mint a replacement session either.
    refresh = real_auth.post(
        "/api/auth/refresh",
        json={"refresh_token": target_tokens["refresh_token"]},
    )
    assert refresh.status_code in (401, 403)

    db = session_factory()
    try:
        assert (
            db.query(RefreshToken)
            .filter(RefreshToken.user_id == target.id)
            .filter(RefreshToken.revoked_at.is_(None))
            .count()
            == 0
        )
    finally:
        db.close()

    # Reactivation restores the same access token: nothing expired, the flag
    # simply flipped back.
    reactivate = real_auth.post(
        f"/api/admin/users/{target.id}/reactivate", headers=admin_headers
    )
    assert reactivate.status_code == 200

    restored = real_auth.get("/api/auth/me", headers=target_headers)
    assert restored.status_code == 200

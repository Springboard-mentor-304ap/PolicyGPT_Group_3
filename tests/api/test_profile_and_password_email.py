"""Item 3: profile update and the password-changed e-mail.

PATCH /auth/me may only touch full_name and phone; the phone is validated and
normalised; the confirmation mail is queued after change-password and
reset-password and can never turn a successful change into an error.
"""

import uuid
from unittest.mock import patch

import pytest

from backend.app.auth.password_reset import (
    create_password_reset_token,
    store_password_reset_token,
)
from backend.app.auth.security import hash_password
from backend.app.models.user import User, UserRole

PASSWORD = "Sup3rSecret1"
MAIL_MODULE = "backend.app.auth.account_emails.send_email"


def _user(seed, phone=None, **overrides):
    fields = dict(
        id=uuid.uuid4(),
        email=f"profile-{uuid.uuid4().hex[:10]}@example.gov",
        password_hash=hash_password(PASSWORD),
        full_name="Original Name",
        phone=phone,
        role=UserRole.CITIZEN,
        email_verified=True,
        is_active=True,
    )
    fields.update(overrides)
    return seed(User(**fields))


def test_patch_me_updates_name_and_phone(api, seed, session_factory):
    user = _user(seed)
    api.login(user)

    response = api.client.patch(
        "/api/auth/me",
        json={"full_name": "  Ada Lovelace  ", "phone": "+91 98765-43210"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["full_name"] == "Ada Lovelace"
    # Normalised: no +91, no spaces, no hyphens.
    assert body["phone"] == "9876543210"

    db = session_factory()
    try:
        stored = db.get(User, user.id)
        assert stored.full_name == "Ada Lovelace"
        assert stored.phone == "9876543210"
    finally:
        db.close()


def test_patch_me_can_clear_the_phone_with_null(api, seed, session_factory):
    user = _user(seed, phone="9876543210")
    api.login(user)

    response = api.client.patch("/api/auth/me", json={"phone": None})

    assert response.status_code == 200
    assert response.json()["phone"] is None

    db = session_factory()
    try:
        assert db.get(User, user.id).phone is None
    finally:
        db.close()


@pytest.mark.parametrize(
    "phone",
    [
        "12345",              # too short
        "12345678901",        # 11 digits
        "abcdefghij",         # not digits at all
        "919876543210",       # country code without the "+"
        "+92 9876543210",     # wrong country code
        "+9198765432109",     # 11 digits behind +91
        "",                   # empty string is not "cleared", it is invalid
    ],
)
def test_patch_me_rejects_invalid_phones(api, seed, phone):
    user = _user(seed)
    api.login(user)

    response = api.client.patch("/api/auth/me", json={"phone": phone})

    assert response.status_code == 422, response.text


def test_patch_me_accepts_the_valid_phone_forms(api, seed):
    user = _user(seed)
    api.login(user)

    for accepted, expected in [
        ("9876543210", "9876543210"),
        ("+919876543210", "9876543210"),
        (" 98765 43210 ", "9876543210"),
        ("+91-98765-43210", "9876543210"),
    ]:
        response = api.client.patch("/api/auth/me", json={"phone": accepted})
        assert response.status_code == 200, (accepted, response.text)
        assert response.json()["phone"] == expected


def test_patch_me_cannot_touch_anything_else(api, seed, session_factory):
    user = _user(seed, phone="9876543210")
    api.login(user)

    response = api.client.patch(
        "/api/auth/me",
        json={
            "full_name": "Only The Name",
            "role": "administrator",
            "email": "someone-else@example.gov",
            "password_hash": "not-a-hash",
            "is_active": False,
            "email_verified": False,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["full_name"] == "Only The Name"
    assert body["role"] == "citizen"
    assert body["email"] == user.email
    assert body["phone"] == "9876543210"
    assert body["is_active"] is True
    assert body["email_verified"] is True

    db = session_factory()
    try:
        stored = db.get(User, user.id)
        assert stored.role == UserRole.CITIZEN
        assert stored.email == user.email
        assert stored.password_hash == user.password_hash
        assert stored.phone == "9876543210"
    finally:
        db.close()


def test_change_password_sends_the_confirmation_email(api, seed):
    user = _user(seed)
    api.login(user)

    with patch(MAIL_MODULE) as send:
        response = api.client.post(
            "/api/auth/change-password",
            json={
                "current_password": PASSWORD,
                "new_password": "EvenB3tter2",
            },
        )

    assert response.status_code == 200, response.text
    send.assert_called_once()
    assert send.call_args.kwargs["to_email"] == user.email
    assert send.call_args.kwargs["subject"] == (
        "Your PolicyGPT password was changed"
    )


def test_change_password_still_fails_on_a_wrong_current_password(api, seed):
    user = _user(seed)
    api.login(user)

    with patch(MAIL_MODULE) as send:
        response = api.client.post(
            "/api/auth/change-password",
            json={
                "current_password": "Wr0ngPass1",
                "new_password": "EvenB3tter2",
            },
        )

    assert response.status_code == 400
    send.assert_not_called()


def test_change_password_survives_a_mail_failure(api, seed):
    user = _user(seed)
    api.login(user)

    with patch(MAIL_MODULE, side_effect=RuntimeError("SMTP is down")):
        response = api.client.post(
            "/api/auth/change-password",
            json={
                "current_password": PASSWORD,
                "new_password": "EvenB3tter2",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["message"] == "Password changed successfully"


def test_reset_password_sends_the_confirmation_email(
    api, seed, session_factory
):
    user = _user(seed)
    reset_token, jti = create_password_reset_token(user.id)

    db = session_factory()
    try:
        store_password_reset_token(db.get(User, user.id), jti)
        db.commit()
    finally:
        db.close()

    with patch(MAIL_MODULE) as send:
        response = api.client.post(
            "/api/auth/reset-password",
            json={
                "reset_token": reset_token,
                "new_password": "Br4ndNew2",
            },
        )

    assert response.status_code == 200, response.text
    send.assert_called_once()
    assert send.call_args.kwargs["to_email"] == user.email


def test_reset_password_survives_a_mail_failure(
    api, seed, session_factory
):
    user = _user(seed)
    reset_token, jti = create_password_reset_token(user.id)

    db = session_factory()
    try:
        store_password_reset_token(db.get(User, user.id), jti)
        db.commit()
    finally:
        db.close()

    with patch(MAIL_MODULE, side_effect=RuntimeError("SMTP is down")):
        response = api.client.post(
            "/api/auth/reset-password",
            json={
                "reset_token": reset_token,
                "new_password": "Br4ndNew2",
            },
        )

    assert response.status_code == 200, response.text

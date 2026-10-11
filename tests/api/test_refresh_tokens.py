"""Item 2: refresh tokens, rotation, logout and revocation.

Every test drives the REAL auth stack (login → tokens → refresh), because the
whole point of the feature is what happens to an actual token: it must be
stored hashed, rotate on every use, die on reuse or logout, and disappear on a
password change or reset.
"""

import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from jose import jwt

from backend.app.auth.password_reset import (
    create_password_reset_token,
    store_password_reset_token,
)
from backend.app.auth.refresh_tokens import cleanup_expired_refresh_tokens
from backend.app.auth.security import ALGORITHM, SECRET_KEY, hash_password
from backend.app.models.refresh_token import RefreshToken
from backend.app.models.user import User, UserRole

PASSWORD = "Sup3rSecret1"


def _user(seed, **overrides):
    fields = dict(
        id=uuid.uuid4(),
        email=f"auth-{uuid.uuid4().hex[:10]}@example.gov",
        password_hash=hash_password(PASSWORD),
        full_name="Refresh Tester",
        role=UserRole.CITIZEN,
        email_verified=True,
        is_active=True,
    )
    fields.update(overrides)
    return seed(User(**fields))


def _login(client, user):
    response = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _refresh(client, token):
    return client.post("/api/auth/refresh", json={"refresh_token": token})


def _decode(token):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


@pytest.fixture()
def password_changed_mail():
    """Swallow the confirmation e-mail so no SMTP connection is attempted."""
    with patch("backend.app.auth.account_emails.send_email") as send:
        yield send


def test_login_stores_a_hashed_jti(real_auth, seed, session_factory):
    user = _user(seed)
    tokens = _login(real_auth, user)

    jti = _decode(tokens["refresh_token"])["jti"]

    db = session_factory()
    try:
        row = (
            db.query(RefreshToken)
            .filter(RefreshToken.user_id == user.id)
            .one()
        )
        # Only the hash is stored — the plaintext jti never reaches the DB.
        assert row.jti_hash == hashlib.sha256(jti.encode("utf-8")).hexdigest()
        assert jti not in row.jti_hash
        assert row.revoked_at is None
        # SQLite hands back a naive UTC timestamp for a tz-aware column.
        stored = row.expires_at
        if stored.tzinfo is None:
            stored = stored.replace(tzinfo=timezone.utc)
        assert stored > datetime.now(timezone.utc)
    finally:
        db.close()


def test_refresh_takes_the_token_in_the_body_and_rotates_it(
    real_auth, seed, session_factory
):
    user = _user(seed)
    tokens = _login(real_auth, user)

    # Old contract (query parameter) is gone: no body, no token.
    as_query = real_auth.post(
        f"/api/auth/refresh?refresh_token={tokens['refresh_token']}"
    )
    assert as_query.status_code == 422

    rotated = _refresh(real_auth, tokens["refresh_token"])
    assert rotated.status_code == 200, rotated.text

    pair = rotated.json()
    assert pair["token_type"] == "bearer"
    # The refresh token rotates; the new access token is a valid 30-minute
    # credential for the same user (identical bytes are possible when two
    # tokens land in the same second, so identity is checked via the claims).
    assert pair["refresh_token"] != tokens["refresh_token"]
    access = _decode(pair["access_token"])
    assert access["type"] == "access"
    assert access["sub"] == str(user.id)

    db = session_factory()
    try:
        rows = (
            db.query(RefreshToken)
            .filter(RefreshToken.user_id == user.id)
            .all()
        )
        assert len(rows) == 2
        assert sum(1 for r in rows if r.revoked_at is not None) == 1
    finally:
        db.close()

    # The retired token cannot be replayed.
    replay = _refresh(real_auth, tokens["refresh_token"])
    assert replay.status_code == 401


def test_reusing_a_rotated_token_revokes_the_whole_chain(real_auth, seed):
    user = _user(seed)
    tokens = _login(real_auth, user)

    rotated = _refresh(real_auth, tokens["refresh_token"])
    assert rotated.status_code == 200
    successor = rotated.json()["refresh_token"]

    # Replay of the retired token: rejected …
    replay = _refresh(real_auth, tokens["refresh_token"])
    assert replay.status_code == 401

    # … and the rest of the chain is dead with it, so a thief and the victim
    # both have to sign in again.
    after_replay = _refresh(real_auth, successor)
    assert after_replay.status_code == 401


def test_logout_revokes_the_refresh_token(real_auth, seed, session_factory):
    user = _user(seed)
    tokens = _login(real_auth, user)

    logout = real_auth.post(
        "/api/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout.status_code == 200

    assert _refresh(real_auth, tokens["refresh_token"]).status_code == 401

    db = session_factory()
    try:
        row = (
            db.query(RefreshToken)
            .filter(RefreshToken.user_id == user.id)
            .one()
        )
        assert row.revoked_at is not None
    finally:
        db.close()

    # Idempotent: an unknown token still logs "out" with the same answer.
    junk = real_auth.post(
        "/api/auth/logout", json={"refresh_token": "not-a-jwt"}
    )
    assert junk.status_code == 200


def test_password_change_revokes_every_refresh_token(
    real_auth, seed, password_changed_mail
):
    user = _user(seed)
    first = _login(real_auth, user)
    second = _login(real_auth, user)

    headers = {"Authorization": f"Bearer {first['access_token']}"}
    changed = real_auth.post(
        "/api/auth/change-password",
        headers=headers,
        json={
            "current_password": PASSWORD,
            "new_password": "EvenB3tter2",
        },
    )
    assert changed.status_code == 200, changed.text

    for token in (first["refresh_token"], second["refresh_token"]):
        assert _refresh(real_auth, token).status_code == 401

    # The confirmation mail was queued for the account owner …
    password_changed_mail.assert_called_once()
    assert password_changed_mail.call_args.kwargs["to_email"] == user.email


def test_password_reset_revokes_every_refresh_token(
    real_auth, seed, session_factory, password_changed_mail
):
    user = _user(seed)
    tokens = _login(real_auth, user)

    reset_token, jti = create_password_reset_token(user.id)

    # Persist the single-use token the way the endpoint would.
    db = session_factory()
    try:
        store_password_reset_token(db.get(User, user.id), jti)
        db.commit()
    finally:
        db.close()

    reset = real_auth.post(
        "/api/auth/reset-password",
        json={"reset_token": reset_token, "new_password": "FreshP4ss2"},
    )
    assert reset.status_code == 200, reset.text

    assert _refresh(real_auth, tokens["refresh_token"]).status_code == 401

    password_changed_mail.assert_called_once()
    assert password_changed_mail.call_args.kwargs["to_email"] == user.email


def test_change_password_does_not_fail_when_the_mail_fails(real_auth, seed):
    user = _user(seed)
    tokens = _login(real_auth, user)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    with patch(
        "backend.app.auth.account_emails.send_email",
        side_effect=RuntimeError("SMTP is down"),
    ):
        changed = real_auth.post(
            "/api/auth/change-password",
            headers=headers,
            json={"current_password": PASSWORD, "new_password": "N3wPass99"},
        )

    assert changed.status_code == 200
    assert changed.json()["message"] == "Password changed successfully"


def test_cleanup_deletes_only_expired_refresh_token_rows(seed, session_factory):
    """The maintenance loop's sweep: expired rows go, live and
    revoked-but-unexpired rows stay (the latter are what detects a replay)."""
    user = _user(seed)
    now = datetime.now(timezone.utc)

    live = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        jti_hash="a" * 64,
        expires_at=now + timedelta(days=7),
    )
    stale = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        jti_hash="b" * 64,
        expires_at=now - timedelta(days=1),
    )
    revoked = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        jti_hash="c" * 64,
        expires_at=now + timedelta(days=6),
        revoked_at=now - timedelta(hours=1),
    )

    db = session_factory()
    try:
        db.add_all([live, stale, revoked])
        db.commit()

        removed = cleanup_expired_refresh_tokens(db)

        assert removed == 1
        remaining = {
            row.jti_hash
            for row in db.query(RefreshToken)
            .filter(RefreshToken.user_id == user.id)
        }
        assert remaining == {"a" * 64, "c" * 64}
    finally:
        db.close()


def test_access_token_lifetime_is_thirty_minutes(real_auth, seed):
    user = _user(seed)
    tokens = _login(real_auth, user)

    payload = _decode(tokens["access_token"])
    remaining = payload["exp"] - time.time()

    # 30 minutes, with a minute of slack for clock and request latency.
    assert 29 * 60 <= remaining <= 30 * 60
    assert payload["type"] == "access"

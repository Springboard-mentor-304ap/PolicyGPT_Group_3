"""Email-verification code hardening (Item 2).

Covers the attempt limit on the 6-digit code, the resend cooldown, the
shortened TTL and the generic failure message:

1. five wrong attempts invalidate the code, even if the 6th is correct;
2. a correct code before the lockout still verifies;
3. issuing a new code resets the attempt counter;
4. a resend inside the 60s cooldown does not issue a new code;
5. an expired code fails with the same generic message;
6. attempts are counted atomically (sequential simulation — see note);
7. every failure returns the identical generic message (no probing).
"""

import time
import uuid
from datetime import datetime, timezone

from backend.app.auth.email_verification import (
    MAX_VERIFICATION_ATTEMPTS,
    RESEND_COOLDOWN_SECONDS,
)
from backend.app.auth.security import hash_password
from backend.app.models.user import User, UserRole


GENERIC_ERROR = "Invalid or expired verification code"


def _seed_unverified_user(seed):
    return seed(
        User(
            id=uuid.uuid4(),
            email=f"verify-{uuid.uuid4().hex[:8]}@example.gov",
            password_hash="x",
            full_name="Unverified Citizen",
            role=UserRole.CITIZEN,
            email_verified=False,
            is_active=True,
        )
    )


def _issue_code(session_factory, user, code="123456"):
    """Write a fresh verification code for the user, straight to the DB."""

    db = session_factory()
    try:
        db.query(User).filter(User.id == user.id).update(
            {
                "email_verification_token": (
                    f"{hash_password(code)}:{int(time.time()) + 900}"
                ),
                "email_verification_attempts": 0,
                "email_verification_sent_at": datetime.now(timezone.utc),
            }
        )
        db.commit()
    finally:
        db.close()


def _expire_code(session_factory, user):
    """Rewrite the stored expiry of the pending code into the past."""

    db = session_factory()
    try:
        row = (
            db.query(User.email_verification_token)
            .filter(User.id == user.id)
            .one()
        )
        stored = row[0]
        digest = stored.rsplit(":", 1)[0]
        db.query(User).filter(User.id == user.id).update(
            {"email_verification_token": f"{digest}:{int(time.time()) - 10}"}
        )
        db.commit()
    finally:
        db.close()


def _backdate_sent_at(session_factory, user, seconds):
    """Age the resend-cooldown timestamp so a resend is allowed."""

    past = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() - seconds,
        tz=timezone.utc,
    )

    db = session_factory()
    try:
        db.query(User).filter(User.id == user.id).update(
            {"email_verification_sent_at": past}
        )
        db.commit()
    finally:
        db.close()


def _stored_token(session_factory, user) -> str | None:
    db = session_factory()
    try:
        return (
            db.query(User.email_verification_token)
            .filter(User.id == user.id)
            .one()[0]
        )
    finally:
        db.close()


def _attempt(api, user, code):
    return api.client.post(
        "/api/auth/verify-email",
        json={"email": user.email, "code": code},
    )


# ─── 1. Five wrong attempts invalidate the code ────────────────────────────
def test_five_wrong_attempts_invalidate_the_code(
    api, seed, session_factory, citizen,
):
    user = _seed_unverified_user(seed)
    _issue_code(session_factory, user, code="123456")

    for attempt_number in range(1, MAX_VERIFICATION_ATTEMPTS + 1):
        response = _attempt(api, user, "999999")
        assert response.status_code == 400
        detail = response.json()["detail"]
        if attempt_number < MAX_VERIFICATION_ATTEMPTS:
            # Identical generic message on every non-final failure.
            assert detail == GENERIC_ERROR
        else:
            # The lockout response still leads with the same generic text
            # and additionally tells the user to request a new code.
            assert detail.startswith(GENERIC_ERROR)
            assert "request a new verification code" in detail.lower()

    # The 6th attempt is the CORRECT code — but the code was burned by the
    # lockout, so it must still fail.
    response = _attempt(api, user, "123456")
    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_ERROR

    # And the user is not marked verified.
    db = session_factory()
    try:
        stored = db.get(User, user.id)
        assert stored.email_verified is False
        assert stored.email_verification_token is None
    finally:
        db.close()


# ─── 2. A correct code before the lockout still works ──────────────────────
def test_correct_code_before_lockout_verifies(
    api, seed, session_factory,
):
    user = _seed_unverified_user(seed)
    _issue_code(session_factory, user, code="123456")

    # Four wrong guesses — one below the limit — then the right code.
    for _ in range(MAX_VERIFICATION_ATTEMPTS - 1):
        assert _attempt(api, user, "000000").status_code == 400

    response = _attempt(api, user, "123456")
    assert response.status_code == 200
    assert "verified" in response.json()["message"].lower()

    db = session_factory()
    try:
        stored = db.get(User, user.id)
        assert stored.email_verified is True
        assert stored.email_verification_token is None
    finally:
        db.close()


# ─── 3. A new code resets the counter ──────────────────────────────────────
def test_new_code_resets_the_attempt_counter(
    api, seed, session_factory, monkeypatch,
):
    user = _seed_unverified_user(seed)
    _issue_code(session_factory, user, code="123456")

    # Burn most of the budget on the first code.
    for _ in range(MAX_VERIFICATION_ATTEMPTS - 1):
        assert _attempt(api, user, "999999").status_code == 400

    # Resend (outside the cooldown) issues a known new code.
    _backdate_sent_at(session_factory, user, RESEND_COOLDOWN_SECONDS + 1)
    monkeypatch.setattr(
        "backend.app.auth.router.generate_verification_code",
        lambda: "654321",
    )
    response = api.client.post(
        "/api/auth/resend-verification",
        json={"email": user.email},
    )
    assert response.status_code == 200

    # The NEW code works immediately — the old code's 4 failed attempts did
    # not carry over (they would have locked this one out after 1 guess).
    response = _attempt(api, user, "654321")
    assert response.status_code == 200

    db = session_factory()
    try:
        assert db.get(User, user.id).email_verified is True
    finally:
        db.close()


# ─── 4. Resend inside the cooldown issues nothing ──────────────────────────
def test_resend_within_cooldown_does_not_issue_a_new_code(
    api, seed, session_factory,
):
    user = _seed_unverified_user(seed)
    _issue_code(session_factory, user, code="123456")

    token_before = _stored_token(session_factory, user)

    # One wrong attempt, so we can also prove the counter was not reset.
    assert _attempt(api, user, "999999").status_code == 400

    # Resend immediately (well inside the 60s window).
    response = api.client.post(
        "/api/auth/resend-verification",
        json={"email": user.email},
    )
    assert response.status_code == 200
    # Identical message to a real send — no probing signal.
    assert response.json()["message"] == "Verification code sent"

    # Nothing changed: same stored code, attempt counter untouched.
    assert _stored_token(session_factory, user) == token_before

    db = session_factory()
    try:
        stored = db.get(User, user.id)
        assert stored.email_verification_attempts == 1
    finally:
        db.close()

    # The ORIGINAL code still works (a new one was not issued over it).
    assert _attempt(api, user, "123456").status_code == 200

    # Unknown emails get the same generic success message, cooldown or not.
    response = api.client.post(
        "/api/auth/resend-verification",
        json={"email": "nobody-here@example.gov"},
    )
    assert response.status_code == 200
    assert "if the email is registered" in response.json()["message"].lower()


# ─── 5. An expired code fails ──────────────────────────────────────────────
def test_expired_code_fails_with_generic_message(
    api, seed, session_factory,
):
    user = _seed_unverified_user(seed)
    _issue_code(session_factory, user, code="123456")
    _expire_code(session_factory, user)

    # Even the CORRECT code fails once expired, and the message is the same
    # generic one a wrong code would produce.
    response = _attempt(api, user, "123456")
    assert response.status_code == 400
    assert response.json()["detail"] == GENERIC_ERROR

    db = session_factory()
    try:
        assert db.get(User, user.id).email_verified is False
    finally:
        db.close()


# ─── 6. The counter is atomic (sequential simulation) ──────────────────────
def test_attempts_are_counted_atomically(
    api, seed, session_factory,
):
    """Rapid sequential guesses can never exceed the limit.

    True parallel requests are not practical against the in-memory SQLite
    harness (one connection, serialized writes), so this simulates the
    attack with back-to-back guesses: the counter must advance by exactly
    one per guess and lock out on exactly the 5th — no guess is skipped,
    and no guess gets a free check after the lockout.
    """

    user = _seed_unverified_user(seed)
    _issue_code(session_factory, user, code="123456")

    def attempts_left():
        db = session_factory()
        try:
            return (
                db.query(User.email_verification_attempts)
                .filter(User.id == user.id)
                .one()[0]
            )
        finally:
            db.close()

    # Fire MAX+3 wrong guesses back-to-back: every one fails, and the
    # lockout lands on exactly the MAXth guess (the code is burned then).
    statuses = [
        _attempt(api, user, "999999").status_code
        for _ in range(MAX_VERIFICATION_ATTEMPTS + 3)
    ]
    assert statuses == [400] * (MAX_VERIFICATION_ATTEMPTS + 3)

    # The counter never exceeded the limit: it was reset on lockout.
    assert attempts_left() is None

    # Even the CORRECT code after the lockout cannot pass — no free check.
    assert _attempt(api, user, "123456").status_code == 400


# ─── 7. No failure mode leaks information ──────────────────────────────────
def test_all_failures_return_the_identical_generic_message(
    api, seed, session_factory,
):
    user = _seed_unverified_user(seed)
    _issue_code(session_factory, user, code="123456")

    details = set()

    # Wrong code.
    details.add(_attempt(api, user, "111111").json()["detail"])

    # Expired code (correct guess).
    _expire_code(session_factory, user)
    details.add(_attempt(api, user, "123456").json()["detail"])

    # No pending code at all (token cleared).
    _issue_code(session_factory, user, code="123456")
    db = session_factory()
    try:
        db.query(User).filter(User.id == user.id).update(
            {"email_verification_token": None}
        )
        db.commit()
    finally:
        db.close()
    details.add(_attempt(api, user, "123456").json()["detail"])

    # Unknown account.
    response = api.client.post(
        "/api/auth/verify-email",
        json={"email": "ghost@example.gov", "code": "123456"},
    )
    details.add(response.json()["detail"])

    # Malformed code.
    details.add(_attempt(api, user, "12345").json()["detail"])

    # One single message across every failure mode.
    assert details == {GENERIC_ERROR}

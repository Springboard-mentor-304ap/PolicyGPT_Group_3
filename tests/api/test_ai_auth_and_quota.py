"""AI endpoint authentication and the per-user daily LLM quota (Item 1).

* anonymous callers get 401 on /api/finder/extract, /api/finder/match and
  /api/helpdesk/chat (helpdesk already required auth before this change);
* any active logged-in role may use them;
* the quota counts LLM calls per user per UTC day and answers 429 past the
  limit; only calls that actually reach the LLM are counted (a helpdesk
  question with no matching knowledge chunks costs nothing);
* /api/finder/match makes no LLM call, so it is never metered.
"""

from types import SimpleNamespace
from unittest.mock import patch

import uuid

from backend.app.ai.quota import (
    FEATURE_FINDER_EXTRACT,
    FEATURE_HELPDESK,
    daily_limit_for,
)
from backend.app.models.ai_daily_usage import AIDailyUsage
from backend.app.models.user import User, UserRole
from tests.api.conftest import _policy, _scheme


class _FakeLLM:
    """Stands in for the Groq-backed client — no network, no key needed."""

    def generate_structured(self, *, system_prompt, user_prompt, response_model):
        # ExtractedProfile requires every key, so populate them explicitly.
        return response_model(
            age=30,
            gender=None,
            annual_income=None,
            occupation=None,
            education=None,
            state=None,
            district=None,
            social_category=None,
            disability_status=None,
        )

    def generate_text(self, *, system_prompt, user_prompt):
        return "A test answer from the knowledge base."


def _fake_chunks():
    chunk = SimpleNamespace(
        id=uuid.uuid4(),
        source_type="scheme",
        title="Test Scheme",
        content="Some scheme content for context.",
    )
    return [(chunk, 0.9)]


# ExtractedProfile requires every key (Optional but no default) and forbids
# extras, so /match payloads must spell out the full shape.
_FULL_PROFILE = {
    "age": 30,
    "gender": None,
    "annual_income": None,
    "occupation": None,
    "education": None,
    "state": None,
    "district": None,
    "social_category": None,
    "disability_status": None,
}


def _usage_rows(session_factory, user_id):
    db = session_factory()
    try:
        return (
            db.query(AIDailyUsage)
            .filter(AIDailyUsage.user_id == user_id)
            .all()
        )
    finally:
        db.close()


# ─── Anonymous callers get 401 ─────────────────────────────────────────────
def test_finder_and_helpdesk_reject_anonymous_callers(real_auth):
    extract = real_auth.post(
        "/api/finder/extract", json={"text": "I am 30 years old"}
    )
    assert extract.status_code == 401

    match = real_auth.post("/api/finder/match", json={"profile": {}})
    assert match.status_code == 401

    chat = real_auth.post(
        "/api/helpdesk/chat", json={"question": "What schemes exist?"}
    )
    # Helpdesk already required auth before this change; asserted here so it
    # stays that way.
    assert chat.status_code == 401


# ─── Any active role may use the endpoints ────────────────────────────────
def test_every_active_role_can_call_the_finder(
    api, seed, session_factory, citizen, official,
):
    researcher = seed(
        User(
            id=uuid.uuid4(),
            email=f"researcher-{uuid.uuid4().hex[:8]}@example.gov",
            password_hash="x",
            full_name="Test Researcher",
            role=UserRole.RESEARCHER,
            email_verified=True,
            is_active=True,
        )
    )

    with patch(
        "backend.app.finder.service.LLMClient", _FakeLLM
    ):
        for user in (citizen, official, researcher):
            api.login(user)
            response = api.client.post(
                "/api/finder/extract",
                json={"text": "I am a 30 year old farmer in Karnataka"},
            )
            assert response.status_code == 200, user.role

            # /match authenticates too and is never metered.
            response = api.client.post(
                "/api/finder/match",
                json={"profile": _FULL_PROFILE},
            )
            assert response.status_code == 200, user.role


# ─── The daily quota: 429 past the limit, per user ────────────────────────
def test_finder_extract_returns_429_past_the_daily_quota(
    api, seed, session_factory, citizen, other_citizen, monkeypatch,
):
    monkeypatch.setenv("AI_DAILY_QUOTA_FINDER_EXTRACT", "2")

    with patch("backend.app.finder.service.LLMClient", _FakeLLM):
        api.login(citizen)

        # Exactly `limit` calls succeed and each is counted once.
        for _ in range(2):
            response = api.client.post(
                "/api/finder/extract",
                json={"text": "I am 30 years old"},
            )
            assert response.status_code == 200

        rows = _usage_rows(session_factory, citizen.id)
        assert len(rows) == 1
        assert rows[0].feature == FEATURE_FINDER_EXTRACT
        assert rows[0].calls == 2

        # The next call is refused with a clear 429...
        response = api.client.post(
            "/api/finder/extract",
            json={"text": "I am 30 years old"},
        )
        assert response.status_code == 429
        detail = response.json()["detail"].lower()
        assert "limit" in detail and "day" in detail

        # ...and does NOT consume quota (only calls that reach the LLM count).
        rows = _usage_rows(session_factory, citizen.id)
        assert rows[0].calls == 2

        # A different user still has their own quota.
        api.login(other_citizen)
        response = api.client.post(
            "/api/finder/extract",
            json={"text": "I am 40 years old"},
        )
        assert response.status_code == 200


def test_helpdesk_quota_counts_only_calls_that_reach_the_llm(
    api, citizen, session_factory, monkeypatch,
):
    monkeypatch.setenv("AI_DAILY_QUOTA_HELPDESK", "1")

    with patch(
        "backend.app.ai.helpdesk_service.retrieve_relevant_chunks",
        lambda *args, **kwargs: [],
    ), patch("backend.app.ai.helpdesk_service.LLMClient", _FakeLLM):
        api.login(citizen)

        # No chunks -> no LLM call -> no quota consumed, friendly answer.
        response = api.client.post(
            "/api/helpdesk/chat",
            json={"question": "Something with no matches"},
        )
        assert response.status_code == 200
        assert _usage_rows(session_factory, citizen.id) == []

    with patch(
        "backend.app.ai.helpdesk_service.retrieve_relevant_chunks",
        lambda *args, **kwargs: _fake_chunks(),
    ), patch("backend.app.ai.helpdesk_service.LLMClient", _FakeLLM):
        # One question reaches the LLM: within the limit.
        response = api.client.post(
            "/api/helpdesk/chat",
            json={"question": "What schemes are available?"},
        )
        assert response.status_code == 200

        rows = _usage_rows(session_factory, citizen.id)
        assert len(rows) == 1
        assert rows[0].feature == FEATURE_HELPDESK
        assert rows[0].calls == 1

        # The second LLM-bound question trips the quota.
        response = api.client.post(
            "/api/helpdesk/chat",
            json={"question": "And another one?"},
        )
        assert response.status_code == 429
        assert "tomorrow" in response.json()["detail"].lower()

        rows = _usage_rows(session_factory, citizen.id)
        assert rows[0].calls == 1


# ─── /finder/match never consumes quota ───────────────────────────────────
def test_finder_match_is_never_metered(
    api, citizen, session_factory, monkeypatch,
):
    monkeypatch.setenv("AI_DAILY_QUOTA_FINDER_EXTRACT", "0")

    api.login(citizen)

    # The extract quota is already exhausted, but /match makes no LLM call
    # and must keep working.
    for _ in range(3):
        response = api.client.post(
            "/api/finder/match",
            json={"profile": _FULL_PROFILE},
        )
        assert response.status_code == 200

    assert _usage_rows(session_factory, citizen.id) == []


# ─── Limit configuration ──────────────────────────────────────────────────
def test_quota_limits_come_from_env_with_defaults(monkeypatch):
    monkeypatch.delenv("AI_DAILY_QUOTA_FINDER_EXTRACT", raising=False)
    monkeypatch.delenv("AI_DAILY_QUOTA_HELPDESK", raising=False)
    assert daily_limit_for(FEATURE_FINDER_EXTRACT) == 30
    assert daily_limit_for(FEATURE_HELPDESK) == 50

    monkeypatch.setenv("AI_DAILY_QUOTA_FINDER_EXTRACT", "7")
    assert daily_limit_for(FEATURE_FINDER_EXTRACT) == 7

    # Garbage falls back to the default instead of crashing.
    monkeypatch.setenv("AI_DAILY_QUOTA_HELPDESK", "not-a-number")
    assert daily_limit_for(FEATURE_HELPDESK) == 50

"""Per-user daily quota on LLM calls (not a rate limiter).

Counts how many LLM calls a user made today (UTC day, so the reset moment is
the same for everyone) and rejects calls past the configured limit with 429.
Limits come from environment variables with built-in defaults:

* ``AI_DAILY_QUOTA_FINDER_EXTRACT`` — /api/finder/extract (default 30)
* ``AI_DAILY_QUOTA_HELPDESK``      — /api/helpdesk/chat  (default 50)

Only calls that actually reach the LLM are counted, and each call is counted
*before* it is made, so a caller cannot exceed the limit even when requests
run concurrently: the increment is a single atomic SQL statement
(``INSERT ... ON CONFLICT DO UPDATE ... RETURNING``) that both inserts the
day's row and bumps the counter, returning the new value in the same
statement. Two racing requests therefore see two different counts and never
both pass the limit check.
"""

import os
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.app.dates import utc_today
from backend.app.models.ai_daily_usage import AIDailyUsage

# Feature keys match the endpoints they guard; limits are env-configurable.
FEATURE_FINDER_EXTRACT = "finder_extract"
FEATURE_HELPDESK = "helpdesk"

_QUOTA_ENV_VARS = {
    FEATURE_FINDER_EXTRACT: ("AI_DAILY_QUOTA_FINDER_EXTRACT", 30),
    FEATURE_HELPDESK: ("AI_DAILY_QUOTA_HELPDESK", 50),
}


def daily_limit_for(feature: str) -> int:
    """Configured daily limit for a feature, from its env var."""

    env_name, default = _QUOTA_ENV_VARS[feature]
    raw = os.getenv(env_name, "").strip()

    try:
        limit = int(raw) if raw else default
    except ValueError:
        limit = default

    return max(0, limit)


def _insert_for(session: Session):
    """The dialect-specific upsert constructor for the active database."""

    dialect = session.get_bind().dialect.name
    return sqlite_insert if dialect == "sqlite" else pg_insert


def consume_llm_quota(
    db: Session,
    user_id,
    feature: str,
) -> None:
    """Count one LLM call for this user today; raise 429 past the limit.

    The counter is incremented before the LLM call is made. When the caller
    is already over the limit the increment is rolled back and 429 is raised,
    so rejected calls never consume quota.
    """

    limit = daily_limit_for(feature)

    today = utc_today()
    now = datetime.now(timezone.utc)
    table = AIDailyUsage.__table__

    statement = (
        _insert_for(db)(table)
        .values(
            user_id=user_id,
            usage_date=today,
            feature=feature,
            calls=1,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["user_id", "usage_date", "feature"],
            set_={"calls": table.c.calls + 1, "updated_at": now},
        )
        .returning(table.c.calls)
    )

    calls = db.execute(statement).scalar_one()

    if calls > limit:
        # Give the rejected call its quota back so only calls that actually
        # reach the LLM are counted.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"You have reached your limit of {limit} AI requests per day "
                f"for this feature. Please try again tomorrow."
            ),
        )

    # Persist the increment before the LLM call runs, exactly as counted.
    db.commit()


def remaining_today(db: Session, user_id, feature: str) -> int:
    """How many calls the user still has left today (informational)."""

    limit = daily_limit_for(feature)

    row = db.execute(
        select(AIDailyUsage.calls).where(
            AIDailyUsage.user_id == user_id,
            AIDailyUsage.usage_date == utc_today(),
            AIDailyUsage.feature == feature,
        )
    ).scalar_one_or_none()

    return max(0, limit - (row or 0))

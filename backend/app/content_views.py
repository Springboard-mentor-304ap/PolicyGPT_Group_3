"""One-view-per-user deduplication for content view counts.

A view only counts the first time a given user reads a given policy or
scheme: the `content_views` composite primary key rejects a second row for
the same (user, content_type, content_id), and the row is flushed in the
same transaction as the `view_count` increment, so concurrent first-view
requests can never double-count (the loser of the insert race receives an
IntegrityError and simply does not increment).

Guests are not counted at all (unchanged behaviour): they have no identity
to deduplicate on, and fingerprinting by IP/user-agent would be both
unreliable and privacy-hostile.
"""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.content_view import ContentView

CONTENT_TYPE_POLICY = "policy"
CONTENT_TYPE_SCHEME = "scheme"


def record_content_view(
    db: Session,
    user_id: UUID,
    content_type: str,
    content_id: UUID,
) -> bool:
    """Record a view attempt; True when this is the user's first view.

    On success the dedup row is flushed (not committed): the caller performs
    the `view_count` increment and commits once, so the dedup row and the
    increment land atomically. A duplicate attempt rolls the session back to
    a clean state and returns False without touching `view_count`.
    """
    existing = db.get(
        ContentView,
        (user_id, content_type, content_id),
    )

    if existing is not None:
        return False

    db.add(
        ContentView(
            user_id=user_id,
            content_type=content_type,
            content_id=content_id,
        )
    )

    try:
        db.flush()
    except IntegrityError:
        # A concurrent request by the same user won the insert race; its
        # increment is already on its way, so this one must not add another.
        db.rollback()
        return False

    return True

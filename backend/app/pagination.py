"""Shared paging bounds for list endpoints.

Every paginated list endpoint behaves the same way — `limit` defaults to
DEFAULT_LIMIT, is clamped to MAX_LIMIT, and the pre-paging total goes out in
an `X-Total-Count` header — so the bounds live in one place instead of
drifting per router.
"""

DEFAULT_LIMIT = 100
MAX_LIMIT = 200


def clamp_limit(limit: int) -> int:
    """Keep a requested page size inside [1, MAX_LIMIT].

    Values above the ceiling are clamped rather than rejected with a 422: a
    client asking for "everything" still gets a valid, bounded page.
    """
    return max(1, min(limit, MAX_LIMIT))

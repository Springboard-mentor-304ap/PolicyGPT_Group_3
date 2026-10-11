"""Write-only audit trail helpers.

`log_action` stages an AuditLog row in the caller's open transaction and
deliberately never commits. The caller's `db.commit()` therefore publishes the
change and its audit entry together: if the operation fails or is rolled back,
no audit row survives to claim it happened.
"""

import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from backend.app.models.audit_log import AuditLog

# Env switch for honouring X-Forwarded-For. Off by default: a client can send
# that header freely, so trusting it blindly would let any caller forge the
# recorded address unless a proxy we control sets it.
TRUSTED_PROXY_ENV = "TRUSTED_PROXY"


def client_ip(request: Request | None) -> str | None:
    """Best-effort client address, or None when the request is unknown.

    X-Forwarded-For is only consulted when TRUSTED_PROXY=true; otherwise the
    socket peer address is used, which a client cannot forge.
    """
    if request is None:
        return None

    trusted = os.getenv(TRUSTED_PROXY_ENV, "").strip().lower() in {
        "true",
        "1",
        "yes",
    }

    if trusted:
        forwarded = request.headers.get("x-forwarded-for", "")
        # Left-most entry is the original client as appended by our proxy.
        candidate = forwarded.split(",")[0].strip()

        if candidate:
            return candidate[:45]

    return request.client.host if request.client else None


def log_action(
    db: Session,
    actor_id: UUID,
    action: str,
    target_table: str,
    target_id: UUID,
    changes: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Stage one audit row. Does not commit — the caller's transaction does.

    `changes` must hold only small, non-secret values (statuses, roles). Never
    put passwords, tokens, hashes or profile data in it.
    """

    audit_log = AuditLog(
        # Stamped here rather than left to the column default: rows written
        # within one second then order correctly, which GET /audit-logs
        # relies on for "newest first".
        created_at=datetime.now(timezone.utc),
        actor_id=actor_id,
        action=action,
        target_table=target_table,
        target_id=target_id,
        changes=changes,
        ip_address=ip_address[:45] if ip_address else None,
    )

    db.add(audit_log)

    return audit_log

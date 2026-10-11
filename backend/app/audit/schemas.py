from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """One audit entry as returned by GET /audit-logs."""

    id: UUID
    actor_id: UUID
    action: str
    target_table: str
    target_id: UUID
    changes: dict[str, Any] | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

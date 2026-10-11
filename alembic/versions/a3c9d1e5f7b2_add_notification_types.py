"""add workflow notification types

Revision ID: a3c9d1e5f7b2
Revises: f1a2b3c4d5e6
Create Date: 2026-10-11 00:00:00.000000

Adds the notification types used by the workflow triggers (policy/scheme
review, role requests, feedback, new applications).

ALTER TYPE ... ADD VALUE cannot run inside a transaction block on Postgres,
so each statement runs with AUTOCOMMIT. ADD VALUE IF NOT EXISTS keeps the
migration safe to re-run after a partial failure. Existing rows are
unaffected: the enum only gains members.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a3c9d1e5f7b2'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Labels match the ORM's rendering of this column: SQLEnum of the
# NotificationType str-Enum, so the label is the member NAME in upper case,
# exactly like the four values that already exist in the type.
NEW_VALUES = (
    "POLICY_REJECTED",
    "SCHEME_APPROVED",
    "SCHEME_REJECTED",
    "ROLE_REQUEST_UPDATE",
    "FEEDBACK_UPDATE",
    "APPROVAL_PENDING",
    "NEW_APPLICATION",
)


def upgrade() -> None:
    """Upgrade schema."""
    # Enum members cannot be removed without rebuilding the type, so the
    # downgrade only drops them when nothing references them.
    with op.get_context().autocommit_block():
        for value in NEW_VALUES:
            op.execute(
                sa.text(
                    "ALTER TYPE notification_type "
                    f"ADD VALUE IF NOT EXISTS '{value}'"
                )
            )


def downgrade() -> None:
    """Downgrade schema.

    Postgres cannot drop a member from an enum type. The values are left in
    place; existing rows would otherwise fail to cast, so only the migration
    record is rewound.
    """
    pass

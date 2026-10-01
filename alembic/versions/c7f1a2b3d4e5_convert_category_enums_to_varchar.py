"""convert policy/scheme category enums to varchar

Revision ID: c7f1a2b3d4e5
Revises: ebb0b29bc991
Create Date: 2026-09-25 10:12:44.918273

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7f1a2b3d4e5'
down_revision: Union[str, Sequence[str], None] = 'ebb0b29bc991'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Original enum labels, exactly as created in:
#   986c720cd48a (policies) and 0e592b013b1d (schemes)
POLICY_CATEGORY_LABELS = (
    'EDUCATION',
    'HEALTHCARE',
    'AGRICULTURE',
    'EMPLOYMENT',
    'FINANCE',
    'WOMEN_CHILD_WELFARE',
    'HOUSING',
    'ENVIRONMENT',
    'DIGITAL_GOVERNANCE',
    'INFRASTRUCTURE',
)

SCHEME_CATEGORY_LABELS = (
    'SCHOLARSHIPS',
    'FARMER_WELFARE',
    'HEALTHCARE',
    'HOUSING',
    'BUSINESS_SUPPORT',
    'WOMEN_EMPOWERMENT',
    'SENIOR_CITIZEN_WELFARE',
    'STUDENT_SCHEMES',
    'EMPLOYMENT_PROGRAMS',
    'SOCIAL_SECURITY',
)

policy_category_type = sa.Enum(*POLICY_CATEGORY_LABELS, name='policy_category')
scheme_category_type = sa.Enum(*SCHEME_CATEGORY_LABELS, name='scheme_category')


def _restore_enum_labels(table: str, labels: tuple[str, ...]) -> None:
    """Map lowercased category values back to their original enum labels.

    Every distinct value must be the exact lowercase form of one of the
    original labels; otherwise this raises instead of guessing a mapping.
    """
    bind = op.get_bind()
    valid = {label.lower(): label for label in labels}
    rows = bind.execute(
        sa.text(f"SELECT DISTINCT category FROM {table} WHERE category IS NOT NULL")
    ).fetchall()
    unexpected = sorted({row[0] for row in rows} - set(valid))
    if unexpected:
        raise RuntimeError(
            f"Cannot restore enum labels for {table}.category: "
            f"values {unexpected!r} do not match any original enum label "
            f"(lowercased or otherwise). Aborting instead of guessing."
        )
    bind.execute(
        sa.text(
            f"UPDATE {table} SET category = upper(category) "
            f"WHERE category IS NOT NULL"
        )
    )


def upgrade() -> None:
    """Upgrade schema."""
    # Convert native enum columns to VARCHAR(100).
    op.alter_column(
        'policies',
        'category',
        existing_type=policy_category_type,
        type_=sa.String(length=100),
        existing_nullable=False,
        postgresql_using='category::varchar',
    )
    op.alter_column(
        'schemes',
        'category',
        existing_type=scheme_category_type,
        type_=sa.String(length=100),
        existing_nullable=False,
        postgresql_using='category::varchar',
    )
    # Audit normalization: category values converted to lowercase.
    op.execute("UPDATE policies SET category = lower(category) WHERE category IS NOT NULL")
    op.execute("UPDATE schemes SET category = lower(category) WHERE category IS NOT NULL")
    # The native enum types are no longer referenced; drop them.
    policy_category_type.drop(op.get_bind(), checkfirst=True)
    scheme_category_type.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate the original native enum types (dropped during upgrade).
    policy_category_type.create(op.get_bind(), checkfirst=True)
    scheme_category_type.create(op.get_bind(), checkfirst=True)
    # Restore original uppercase labels, verifying the mapping for every value.
    _restore_enum_labels('policies', POLICY_CATEGORY_LABELS)
    _restore_enum_labels('schemes', SCHEME_CATEGORY_LABELS)
    # Convert VARCHAR(100) columns back to the native enum types.
    op.alter_column(
        'policies',
        'category',
        existing_type=sa.String(length=100),
        type_=policy_category_type,
        existing_nullable=False,
        postgresql_using='category::policy_category',
    )
    op.alter_column(
        'schemes',
        'category',
        existing_type=sa.String(length=100),
        type_=scheme_category_type,
        existing_nullable=False,
        postgresql_using='category::scheme_category',
    )

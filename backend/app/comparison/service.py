from sqlalchemy.orm import Session

from backend.app.eligibility.formatting import format_rule
from backend.app.models.eligibility_rule import EligibilityRule
from backend.app.models.policy import Policy, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.comparison.schemas import ComparisonItem, ComparisonType, ComparisonRequest

def compare_items(
        db: Session,
        request: ComparisonRequest,
) -> list[ComparisonItem]:

    # Deduplicate first (keeping the requested order): the not-found check
    # below compares the returned rows against this list, so a repeated id
    # used to make it fail with a 404 even though every item existed.
    unique_ids = list(dict.fromkeys(request.ids))

    if request.type == ComparisonType.POLICY:
        return compare_policies(db, unique_ids)

    return compare_schemes(db, unique_ids)

def compare_policies(
        db: Session,
        ids: list,
) -> list[ComparisonItem]:

    policies = (
        db.query(Policy)
        .filter(
            Policy.id.in_(ids),
            Policy.status == PolicyStatus.APPROVED,
        )
        .all()
    )

    if len(policies) != len(ids):
        raise ValueError("One or more policies were not found.")

    policy_map = {policy.id: policy for policy in policies}

    return [
        ComparisonItem(
            id=policy_map[policy_id].id,
            title=policy_map[policy_id].title,
            description=policy_map[policy_id].description,
            type=ComparisonType.POLICY,
            category=policy_map[policy_id].category.value,
            department=policy_map[policy_id].department,
            ministry=policy_map[policy_id].ministry,
            state=policy_map[policy_id].state,
            status=policy_map[policy_id].status.value,
            benefits=None,
            eligibility=[],
            application_process=None,
            launch_date = (
                policy_map[policy_id].published_date.isoformat()
                if policy_map[policy_id].published_date
                else None
            ),
            deadline_date=None,
            document_url=policy_map[policy_id].document_url,
        )
        for policy_id in ids
    ]


def compare_schemes(
    db: Session,
    ids: list,
) -> list[ComparisonItem]:

    schemes = (
        db.query(Scheme)
        .filter(
            Scheme.id.in_(ids),
            Scheme.status == SchemeStatus.ACTIVE,
        )
        .all()
    )

    if len(schemes) != len(ids):
        raise ValueError("One or more schemes were not found.")

    scheme_map = {scheme.id: scheme for scheme in schemes}

    results = []

    for scheme_id in ids:
        scheme = scheme_map[scheme_id]

        rules = (
            db.query(EligibilityRule)
            .filter(EligibilityRule.scheme_id == scheme.id)
            .all()
        )

        # Human-readable rules ("Age: 18 or above"), not the raw
        # "age gte 18" triple the engine stores.
        eligibility = [
            format_rule(rule.parameter, rule.operator, rule.value)
            for rule in rules
        ]

        results.append(
            ComparisonItem(
                id=scheme.id,
                title=scheme.title,
                description=scheme.description,
                type=ComparisonType.SCHEME,
                category=scheme.category.value,
                department=scheme.department,
                ministry=None,
                state=scheme.state,
                status=scheme.status.value,
                benefits=scheme.benefits,
                eligibility=eligibility,
                application_process=scheme.application_process,
                launch_date=(
                    scheme.launch_date.isoformat()
                    if scheme.launch_date
                    else None
                ),
                deadline_date=(
                    scheme.deadline_date.isoformat()
                    if scheme.deadline_date
                    else None
                ),
                document_url=scheme.document_url,
            )
        )

    return results
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.ai.embedding_service import generate_embedding
from backend.app.models.eligibility_rule import EligibilityRule
from backend.app.models.policy import Policy, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeStatus
from backend.app.models.knowledge_chunk import KnowledgeChunk


OPERATOR_LABELS = {
    "eq": "must be",
    "neq": "must not be",
    "lt": "must be less than",
    "lte": "must be less than or equal to",
    "gt": "must be greater than",
    "gte": "must be greater than or equal to",
    "in": "must be one of",
    "not_in": "must not be one of",
}


def _format_list(values: list[str] | None) -> str:
    if not values:
        return "Not specified"

    return "\n".join(f"- {value}" for value in values)


def _format_rule(rule: EligibilityRule) -> str:
    parameter = rule.parameter.value.replace("_", " ").title()
    operator = OPERATOR_LABELS.get(
        rule.operator.value,
        rule.operator.value,
    )

    return f"- {parameter} {operator} {rule.value}"


def _build_policy_content(policy: Policy) -> str:
    sections = [
        f"Policy: {policy.title}",
        "",
        "Description:",
        policy.description,
        "",
        f"Category: {policy.category.value}",
        f"Department: {policy.department}",
    ]

    if policy.ministry:
        sections.append(f"Ministry: {policy.ministry}")

    if policy.state:
        sections.append(f"State: {policy.state}")

    if policy.published_date:
        sections.append(
            f"Published date: {policy.published_date.isoformat()}"
        )

    sections.extend(
        [
            "",
            "Required documents:",
            _format_list(policy.required_documents),
        ]
    )

    return "\n".join(sections)


def _build_scheme_content(
    scheme: Scheme,
    rules: list[EligibilityRule],
) -> str:
    sections = [
        f"Scheme: {scheme.title}",
        "",
        "Description:",
        scheme.description,
        "",
        f"Category: {scheme.category.value}",
    ]

    if scheme.department:
        sections.append(f"Department: {scheme.department}")

    if scheme.state:
        sections.append(f"State: {scheme.state}")

    if scheme.launch_date:
        sections.append(
            f"Launch date: {scheme.launch_date.isoformat()}"
        )

    if scheme.deadline_date:
        sections.append(
            f"Deadline date: {scheme.deadline_date.isoformat()}"
        )

    sections.extend(
        [
            "",
            "Benefits:",
            _format_list(scheme.benefits),
            "",
            "Application process:",
            scheme.application_process or "Not specified",
            "",
            "Required documents:",
            _format_list(scheme.required_documents),
        ]
    )

    if rules:
        sections.extend(
            [
                "",
                "Eligibility requirements:",
                *[_format_rule(rule) for rule in rules],
            ]
        )

    return "\n".join(sections)


def _upsert_chunk(
    db: Session,
    *,
    source_type: str,
    source_id: UUID,
    title: str,
    content: str,
    chunk_index: int,
) -> KnowledgeChunk:
    existing = db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.source_type == source_type,
            KnowledgeChunk.source_id == source_id,
            KnowledgeChunk.chunk_index == chunk_index,
        )
    ).scalar_one_or_none()

    embedding = generate_embedding(content)

    if existing:
        existing.title = title
        existing.content = content
        existing.embedding = embedding
        return existing

    chunk = KnowledgeChunk(
        source_type=source_type,
        source_id=source_id,
        title=title,
        content=content,
        chunk_index=chunk_index,
        embedding=embedding,
    )

    db.add(chunk)
    return chunk


def ingest_knowledge_base(db: Session) -> dict[str, int]:
    policies = db.execute(
        select(Policy).where(
            Policy.status == PolicyStatus.APPROVED
        )
    ).scalars().all()

    schemes = db.execute(
        select(Scheme).where(
            Scheme.status == SchemeStatus.ACTIVE
        )
    ).scalars().all()

    policy_count = 0
    scheme_count = 0

    for policy in policies:
        _upsert_chunk(
            db,
            source_type="policy",
            source_id=policy.id,
            title=policy.title,
            content=_build_policy_content(policy),
            chunk_index=0,
        )
        policy_count += 1

    for scheme in schemes:
        rules = db.execute(
            select(EligibilityRule)
            .where(EligibilityRule.scheme_id == scheme.id)
            .order_by(EligibilityRule.created_at)
        ).scalars().all()

        _upsert_chunk(
            db,
            source_type="scheme",
            source_id=scheme.id,
            title=scheme.title,
            content=_build_scheme_content(scheme, rules),
            chunk_index=0,
        )
        scheme_count += 1

    db.commit()

    return {
        "policies": policy_count,
        "schemes": scheme_count,
        "total": policy_count + scheme_count,
    }
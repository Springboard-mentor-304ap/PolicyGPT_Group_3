"""Knowledge-base ingestion for the AI Helpdesk.

Single source of truth for turning APPROVED policies and ACTIVE schemes into
``knowledge_chunks`` rows (title, content, 384-dim embedding) that pgvector
retrieval searches. Two entry points share the same upsert logic:

* ``sync_policy_knowledge`` / ``sync_scheme_knowledge`` — per-record
  synchronization triggered automatically after each policy/scheme
  transaction commits (see ``backend.app.ai.sync_service``).
* ``ingest_knowledge_base`` — full ingestion with reconciliation: it
  (re)indexes every eligible record and removes chunks whose policy/scheme is
  no longer eligible. Cleanup is scoped strictly to ``source_type``
  ``policy``/``scheme`` so unrelated chunk records are never deleted.

Full backfill, rebuild, or post-incident reconciliation — run from the
repository root so ``.env`` provides ``DATABASE_URL``::

    python -m backend.app.ai.knowledge_ingestion

Add ``--no-remove-stale`` to re-index without deleting stale chunks.
"""

import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.ai.embedding_service import generate_embedding
from backend.app.eligibility.formatting import format_rule
from backend.app.models.eligibility_rule import EligibilityRule
from backend.app.models.knowledge_chunk import KnowledgeChunk
from backend.app.models.policy import Policy, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeStatus

logger = logging.getLogger(__name__)


def _normalize_datetime(dt: datetime | str | None) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _format_list(values: list[str] | None) -> str:
    if not values:
        return "Not specified"

    return "\n".join(f"- {value}" for value in values)


def _format_rule(rule: EligibilityRule) -> str:
    # Shared formatter: one human-readable wording for every place that shows
    # a rule (comparison endpoint, knowledge chunks).
    return f"- {format_rule(rule.parameter, rule.operator, rule.value)}"


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
    chunk_index: int = 0,
    source_updated_at: datetime | None = None,
) -> KnowledgeChunk:
    existing = db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.source_type == source_type,
            KnowledgeChunk.source_id == source_id,
            KnowledgeChunk.chunk_index == chunk_index,
        )
    ).scalar_one_or_none()

    meta = {
        "source_updated_at": source_updated_at.isoformat() if source_updated_at else None
    }

    if existing:
        existing_meta = existing.chunk_metadata or {}
        existing_ts = _normalize_datetime(existing_meta.get("source_updated_at"))
        incoming_ts = _normalize_datetime(source_updated_at)
        if existing_ts and incoming_ts and existing_ts > incoming_ts:
            logger.info(
                "Skipping stale chunk update for %s %s: existing is newer (%s > %s)",
                source_type, source_id, existing_ts, incoming_ts,
            )
            return existing

        # Remove any unexpected duplicate chunks for this source with different chunk indices
        db.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.source_type == source_type,
                KnowledgeChunk.source_id == source_id,
                KnowledgeChunk.chunk_index != chunk_index,
            )
        )

        # If content and title are unchanged, avoid regenerating embedding
        if existing.title == title and existing.content == content:
            existing.chunk_metadata = meta
            return existing

        embedding = generate_embedding(content)
        existing.title = title
        existing.content = content
        existing.embedding = embedding
        existing.chunk_metadata = meta
        return existing

    # Remove any extra chunks for this source if they exist
    db.execute(
        delete(KnowledgeChunk).where(
            KnowledgeChunk.source_type == source_type,
            KnowledgeChunk.source_id == source_id,
            KnowledgeChunk.chunk_index != chunk_index,
        )
    )

    embedding = generate_embedding(content)
    chunk = KnowledgeChunk(
        id=uuid.uuid4(),
        source_type=source_type,
        source_id=source_id,
        title=title,
        content=content,
        chunk_index=chunk_index,
        chunk_metadata=meta,
        embedding=embedding,
    )

    db.add(chunk)
    return chunk


def remove_knowledge_chunks(
    db: Session,
    source_type: str,
    source_id: UUID,
) -> int:
    """Remove all knowledge base chunks associated with a specific source record."""
    stmt = delete(KnowledgeChunk).where(
        KnowledgeChunk.source_type == source_type,
        KnowledgeChunk.source_id == source_id,
    )
    result = db.execute(stmt)
    return result.rowcount or 0


def sync_policy_knowledge(
    db: Session,
    policy_id: UUID,
    *,
    expected_updated_at: datetime | None = None,
) -> dict:
    """Synchronize a single policy record into the knowledge base.

    If the policy is deleted or not APPROVED, removes any existing chunks.
    If APPROVED, checks for freshness, updates chunk and embedding, and commits.
    """
    policy = db.get(Policy, policy_id)

    if policy is None or policy.status != PolicyStatus.APPROVED:
        removed_count = remove_knowledge_chunks(db, "policy", policy_id)
        db.commit()
        status_detail = policy.status.value if policy else "deleted"
        return {
            "source_type": "policy",
            "source_id": policy_id,
            "status": "success",
            "action": "removed" if removed_count > 0 else "noop",
            "details": f"Policy not eligible (status: {status_detail}), removed {removed_count} chunk(s)",
        }

    # Stale job check: if the database record was already updated after this job was queued
    if expected_updated_at and policy.updated_at:
        exp_ts = _normalize_datetime(expected_updated_at)
        pol_ts = _normalize_datetime(policy.updated_at)
        if exp_ts and pol_ts and pol_ts > exp_ts:
            logger.info(
                "Stale job for policy %s skipped (current %s > job %s)",
                policy_id, pol_ts, exp_ts,
            )
            return {
                "source_type": "policy",
                "source_id": policy_id,
                "status": "skipped_stale",
                "action": "noop",
                "details": "Job is stale, newer record already committed",
            }

    content = _build_policy_content(policy)
    existing = db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.source_type == "policy",
            KnowledgeChunk.source_id == policy.id,
            KnowledgeChunk.chunk_index == 0,
        )
    ).scalar_one_or_none()

    _upsert_chunk(
        db,
        source_type="policy",
        source_id=policy.id,
        title=policy.title,
        content=content,
        chunk_index=0,
        source_updated_at=policy.updated_at,
    )
    db.commit()

    action = "updated" if existing else "indexed"
    return {
        "source_type": "policy",
        "source_id": policy_id,
        "status": "success",
        "action": action,
        "details": f"Policy successfully {action}",
    }


def sync_scheme_knowledge(
    db: Session,
    scheme_id: UUID,
    *,
    expected_updated_at: datetime | None = None,
) -> dict:
    """Synchronize a single scheme record into the knowledge base.

    If the scheme is deleted or not ACTIVE, removes any existing chunks.
    If ACTIVE, fetches rules, updates chunk and embedding, and commits.
    """
    scheme = db.get(Scheme, scheme_id)

    if scheme is None or scheme.status != SchemeStatus.ACTIVE:
        removed_count = remove_knowledge_chunks(db, "scheme", scheme_id)
        db.commit()
        status_detail = scheme.status.value if scheme else "deleted"
        return {
            "source_type": "scheme",
            "source_id": scheme_id,
            "status": "success",
            "action": "removed" if removed_count > 0 else "noop",
            "details": f"Scheme not eligible (status: {status_detail}), removed {removed_count} chunk(s)",
        }

    # Stale job check: if the database record was already updated after this job was queued
    if expected_updated_at and scheme.updated_at:
        exp_ts = _normalize_datetime(expected_updated_at)
        sch_ts = _normalize_datetime(scheme.updated_at)
        if exp_ts and sch_ts and sch_ts > exp_ts:
            logger.info(
                "Stale job for scheme %s skipped (current %s > job %s)",
                scheme_id, sch_ts, exp_ts,
            )
            return {
                "source_type": "scheme",
                "source_id": scheme_id,
                "status": "skipped_stale",
                "action": "noop",
                "details": "Job is stale, newer record already committed",
            }

    rules = db.execute(
        select(EligibilityRule)
        .where(EligibilityRule.scheme_id == scheme.id)
        .order_by(EligibilityRule.created_at)
    ).scalars().all()

    content = _build_scheme_content(scheme, rules)
    existing = db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.source_type == "scheme",
            KnowledgeChunk.source_id == scheme.id,
            KnowledgeChunk.chunk_index == 0,
        )
    ).scalar_one_or_none()

    _upsert_chunk(
        db,
        source_type="scheme",
        source_id=scheme.id,
        title=scheme.title,
        content=content,
        chunk_index=0,
        source_updated_at=scheme.updated_at,
    )
    db.commit()

    action = "updated" if existing else "indexed"
    return {
        "source_type": "scheme",
        "source_id": scheme_id,
        "status": "success",
        "action": action,
        "details": f"Scheme successfully {action}",
    }


def ingest_knowledge_base(
    db: Session,
    remove_stale: bool = True,
) -> dict[str, int]:
    """Ingest and reconcile all eligible policies and schemes in the database.

    When remove_stale is True, deletes orphaned chunks for policies and schemes
    that are no longer eligible, while leaving all unrelated chunk records intact.
    """
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
            source_updated_at=policy.updated_at,
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
            source_updated_at=scheme.updated_at,
        )
        scheme_count += 1

    removed_policies = 0
    removed_schemes = 0

    if remove_stale:
        approved_policy_ids = [p.id for p in policies]
        active_scheme_ids = [s.id for s in schemes]

        # Only clean chunks with source_type == "policy"
        if approved_policy_ids:
            policy_stale_stmt = delete(KnowledgeChunk).where(
                KnowledgeChunk.source_type == "policy",
                KnowledgeChunk.source_id.not_in(approved_policy_ids),
            )
        else:
            policy_stale_stmt = delete(KnowledgeChunk).where(
                KnowledgeChunk.source_type == "policy",
            )
        res_p = db.execute(policy_stale_stmt)
        removed_policies = res_p.rowcount or 0

        # Only clean chunks with source_type == "scheme"
        if active_scheme_ids:
            scheme_stale_stmt = delete(KnowledgeChunk).where(
                KnowledgeChunk.source_type == "scheme",
                KnowledgeChunk.source_id.not_in(active_scheme_ids),
            )
        else:
            scheme_stale_stmt = delete(KnowledgeChunk).where(
                KnowledgeChunk.source_type == "scheme",
            )
        res_s = db.execute(scheme_stale_stmt)
        removed_schemes = res_s.rowcount or 0

    db.commit()

    return {
        "policies": policy_count,
        "schemes": scheme_count,
        "removed_policies": removed_policies,
        "removed_schemes": removed_schemes,
        "total": policy_count + scheme_count,
    }


if __name__ == "__main__":
    import argparse
    import sys
    from backend.app.db.database import SessionLocal

    parser = argparse.ArgumentParser(
        description="PolicyGPT Knowledge Base Ingestion & Reconciliation CLI"
    )
    parser.add_argument(
        "--no-remove-stale",
        action="store_true",
        help="Skip removing stale chunks for unapproved/inactive records",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    db = SessionLocal()
    try:
        print("Starting full knowledge base ingestion & reconciliation...")
        result = ingest_knowledge_base(
            db,
            remove_stale=not args.no_remove_stale,
        )
        print(
            f"Knowledge base synchronization finished successfully:\n"
            f"  - Active policies indexed: {result['policies']}\n"
            f"  - Active schemes indexed:  {result['schemes']}\n"
            f"  - Stale policy chunks removed: {result['removed_policies']}\n"
            f"  - Stale scheme chunks removed: {result['removed_schemes']}\n"
            f"  - Total active items: {result['total']}"
        )
    except Exception as exc:
        print(f"Ingestion failed with error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()
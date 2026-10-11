import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector

from backend.app.db.database import Base
from backend.app.models.user import User, UserRole
from backend.app.models.policy import Policy, PolicyStatus, PolicyCategory
from backend.app.models.scheme import Scheme, SchemeStatus, SchemeCategory
from backend.app.models.eligibility_rule import (
    EligibilityRule,
    EligibilityParameter,
    EligibilityOperator,
)
from backend.app.models.knowledge_chunk import KnowledgeChunk
from backend.app.models.government_official_profile import GovernmentOfficialProfile
from backend.app.ai.knowledge_ingestion import (
    ingest_knowledge_base,
    sync_policy_knowledge,
    sync_scheme_knowledge,
    remove_knowledge_chunks,
)
from backend.app.ai.sync_service import (
    sync_source_record,
    schedule_policy_sync,
    schedule_scheme_sync,
    retry_sync,
    retry_failed_syncs,
    wait_for_sync_tasks,
    get_sync_status,
    get_failed_syncs,
    clear_sync_registry,
    SyncStatus,
    SyncAction,
)
from backend.app.policies.service import (
    approve_policy,
    archive_policy,
    reject_policy,
)
from backend.app.schemes.service import (
    approve_scheme,
    archive_scheme,
    reject_scheme,
    create_eligibility_rule,
)
from backend.app.ai.retrieval_service import retrieve_relevant_chunks
from backend.app.ai.helpdesk_service import answer_helpdesk_question


# Configure SQLite to emulate Postgres types for fast, self-contained unit testing
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_, compiler, **kw):
    return "JSON"


def dummy_embedding(text: str) -> list[float]:
    """Deterministic dummy 384-dimensional embedding."""
    val = float(len(text) % 100) / 100.0
    return [val] * 384


@pytest.fixture(autouse=True)
def mock_embedding_generation():
    """Ensure tests never call the heavy sentence-transformers model over network."""
    with patch("backend.app.ai.knowledge_ingestion.generate_embedding", side_effect=dummy_embedding) as mock:
        with patch("backend.app.ai.embedding_service.generate_embedding", side_effect=dummy_embedding):
            yield mock


@pytest.fixture
def db_session():
    """Create a fresh in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        dbapi_connection.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    clear_sync_registry()

    yield session

    session.close()
    clear_sync_registry()


@pytest.fixture
def admin_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email="admin@policygpt.gov",
        password_hash="fakehash",
        full_name="Admin Official",
        role=UserRole.ADMINISTRATOR,
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def official_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email="official@policygpt.gov",
        password_hash="fakehash",
        full_name="Gov Official",
        role=UserRole.GOVERNMENT_OFFICIAL,
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


# 1. An approved policy is automatically indexed.
def test_approved_policy_is_automatically_indexed(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="National Digital Health Mission",
        description="Comprehensive healthcare digitization for all citizens.",
        category=PolicyCategory.HEALTHCARE,
        department="Health",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    res = sync_policy_knowledge(db_session, policy.id)
    assert res["status"] == "success"
    assert res["action"] == "indexed"

    chunk = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .first()
    )
    assert chunk is not None
    assert chunk.title == "National Digital Health Mission"
    assert "National Digital Health Mission" in chunk.content
    assert len(chunk.embedding) == 384


# 2. A draft policy is not indexed.
def test_draft_policy_is_not_indexed(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Draft Cyber Policy",
        description="Internal proposal for cybersecurity guidelines.",
        category=PolicyCategory.DIGITAL_GOVERNANCE,
        department="IT",
        status=PolicyStatus.DRAFT,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    res = sync_policy_knowledge(db_session, policy.id)
    assert res["status"] == "success"
    assert res["action"] == "noop"

    chunk = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .first()
    )
    assert chunk is None


# 3. A pending policy is not indexed.
def test_pending_policy_is_not_indexed(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Pending Water Policy",
        description="Clean water distribution scheme proposal.",
        category=PolicyCategory.INFRASTRUCTURE,
        department="Water Resources",
        status=PolicyStatus.PENDING_APPROVAL,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    res = sync_policy_knowledge(db_session, policy.id)
    assert res["status"] == "success"
    assert res["action"] == "noop"

    count = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .count()
    )
    assert count == 0


# 4. An active scheme is automatically indexed.
def test_active_scheme_is_automatically_indexed(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Education For All Policy",
        description="Universal education.",
        category=PolicyCategory.EDUCATION,
        department="Education",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    scheme = Scheme(
        id=uuid.uuid4(),
        policy_id=policy.id,
        title="National Merit Scholarship",
        description="Scholarship for meritorious students.",
        category=SchemeCategory.SCHOLARSHIPS,
        department="Education",
        status=SchemeStatus.ACTIVE,
        benefits=["Tuition fee waiver", "Monthly stipend"],
        created_by=admin_user.id,
    )
    db_session.add(scheme)
    db_session.commit()

    rule = EligibilityRule(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        parameter=EligibilityParameter.AGE,
        operator=EligibilityOperator.LTE,
        value="25",
    )
    db_session.add(rule)
    db_session.commit()

    res = sync_scheme_knowledge(db_session, scheme.id)
    assert res["status"] == "success"
    assert res["action"] == "indexed"

    chunk = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "scheme", KnowledgeChunk.source_id == scheme.id)
        .first()
    )
    assert chunk is not None
    assert chunk.title == "National Merit Scholarship"
    assert "Tuition fee waiver" in chunk.content
    # Rules are rendered with the shared human-readable formatter.
    assert "Age: 25 or below" in chunk.content


# 5. An inactive/ineligible scheme is not indexed.
def test_inactive_scheme_is_not_indexed(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Housing Policy",
        description="Affordable housing.",
        category=PolicyCategory.HOUSING,
        department="Housing",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    scheme = Scheme(
        id=uuid.uuid4(),
        policy_id=policy.id,
        title="Pending Rural Housing Scheme",
        description="Housing subsidy proposal.",
        category=SchemeCategory.HOUSING,
        department="Housing",
        status=SchemeStatus.PENDING_APPROVAL,
        created_by=admin_user.id,
    )
    db_session.add(scheme)
    db_session.commit()

    res = sync_scheme_knowledge(db_session, scheme.id)
    assert res["action"] == "noop"

    count = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "scheme", KnowledgeChunk.source_id == scheme.id)
        .count()
    )
    assert count == 0


# 6. Editing an indexed policy refreshes its content and embedding.
def test_editing_indexed_policy_refreshes_content(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Original Energy Policy",
        description="Renewable targets for 2026.",
        category=PolicyCategory.ENVIRONMENT,
        department="Energy",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    sync_policy_knowledge(db_session, policy.id)
    chunk = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .one()
    )
    assert chunk.title == "Original Energy Policy"

    # Edit policy
    policy.title = "Updated Green Energy Policy 2030"
    policy.description = "Updated renewable solar and wind targets."
    policy.updated_at = datetime.now(timezone.utc)
    db_session.commit()

    res = sync_policy_knowledge(db_session, policy.id)
    assert res["action"] == "updated"

    # Verify chunk was updated in-place (no duplicate)
    chunks = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .all()
    )
    assert len(chunks) == 1
    assert chunks[0].title == "Updated Green Energy Policy 2030"
    assert "Updated renewable solar" in chunks[0].content


# 7. Editing an indexed scheme refreshes its content and embedding.
def test_editing_indexed_scheme_refreshes_content(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Agriculture Policy",
        description="Farmer support.",
        category=PolicyCategory.AGRICULTURE,
        department="Agriculture",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    scheme = Scheme(
        id=uuid.uuid4(),
        policy_id=policy.id,
        title="Crop Insurance Scheme",
        description="Coverage for drought and floods.",
        category=SchemeCategory.FARMER_WELFARE,
        department="Agriculture",
        status=SchemeStatus.ACTIVE,
        benefits=["50% premium subsidy"],
        created_by=admin_user.id,
    )
    db_session.add(scheme)
    db_session.commit()

    sync_scheme_knowledge(db_session, scheme.id)
    chunk = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "scheme", KnowledgeChunk.source_id == scheme.id)
        .one()
    )
    assert "50% premium subsidy" in chunk.content

    # Add eligibility rule to the scheme
    new_rule = EligibilityRule(
        id=uuid.uuid4(),
        scheme_id=scheme.id,
        parameter=EligibilityParameter.INCOME,
        operator=EligibilityOperator.LTE,
        value="300000",
    )
    db_session.add(new_rule)
    scheme.updated_at = datetime.now(timezone.utc)
    db_session.commit()

    sync_scheme_knowledge(db_session, scheme.id)

    chunks = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "scheme", KnowledgeChunk.source_id == scheme.id)
        .all()
    )
    assert len(chunks) == 1
    assert "Income: 300000 or below" in chunks[0].content


# 8. Changing an eligible record to an ineligible status removes its chunks.
def test_changing_eligible_to_ineligible_removes_chunks(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Subsidized Housing 2026",
        description="Housing policy.",
        category=PolicyCategory.HOUSING,
        department="Housing",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    sync_policy_knowledge(db_session, policy.id)
    assert (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .count()
        == 1
    )

    # Archive the policy
    policy.status = PolicyStatus.ARCHIVED
    db_session.commit()

    res = sync_policy_knowledge(db_session, policy.id)
    assert res["action"] == "removed"
    assert (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .count()
        == 0
    )


# 9. Repeated synchronization does not create duplicates.
def test_repeated_synchronization_is_idempotent(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Repeat Sync Policy",
        description="Testing idempotency.",
        category=PolicyCategory.EDUCATION,
        department="Education",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    # Synchronize 3 times
    sync_policy_knowledge(db_session, policy.id)
    sync_policy_knowledge(db_session, policy.id)
    sync_policy_knowledge(db_session, policy.id)

    chunks = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .all()
    )
    assert len(chunks) == 1


# 10. A synchronization failure is logged and can be retried.
def test_synchronization_failure_logged_and_can_be_retried(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Failing Sync Policy",
        description="Testing error handling.",
        category=PolicyCategory.FINANCE,
        department="Finance",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    # Simulate embedding failure
    with patch(
        "backend.app.ai.knowledge_ingestion.generate_embedding",
        side_effect=RuntimeError("Embedding generator failed"),
    ):
        with pytest.raises(RuntimeError):
            sync_source_record("policy", policy.id, db=db_session)

    # Failure should be tracked in sync registry
    status = get_sync_status("policy", policy.id)
    assert status is not None
    assert status.status == SyncStatus.FAILED
    assert "Embedding generator failed" in status.error
    assert len(get_failed_syncs()) == 1

    # Retry should succeed once the error is cleared
    retry_sync("policy", policy.id, db=db_session, background=False)

    status_after = get_sync_status("policy", policy.id)
    assert status_after.status == SyncStatus.SUCCESS
    assert (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .count()
        == 1
    )


# 11. A stale job cannot overwrite a newer committed version.
def test_stale_job_cannot_overwrite_newer_committed_version(db_session, admin_user):
    t_early = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    policy = Policy(
        id=uuid.uuid4(),
        title="Policy V2",
        description="Committed version 2.",
        category=PolicyCategory.EMPLOYMENT,
        department="Labor",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
        updated_at=t_late,
    )
    db_session.add(policy)
    db_session.commit()

    # Index latest version first
    sync_policy_knowledge(db_session, policy.id)
    chunk = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .one()
    )
    assert chunk.title == "Policy V2"

    # Now simulate a delayed job for t_early running
    res = sync_policy_knowledge(db_session, policy.id, expected_updated_at=t_early)
    assert res["status"] == "skipped_stale"
    assert res["action"] == "noop"

    # Verify chunk was NOT overwritten
    chunk_after = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .one()
    )
    assert chunk_after.title == "Policy V2"


# 12. A delayed indexing job cannot reinsert a record that has become ineligible.
def test_delayed_indexing_job_cannot_reinsert_ineligible_record(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Delayed Job Ineligible Policy",
        description="Was approved, now archived.",
        category=PolicyCategory.EDUCATION,
        department="Education",
        status=PolicyStatus.ARCHIVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    # A delayed job that was queued when the policy was approved executes now
    res = sync_policy_knowledge(db_session, policy.id)
    assert res["action"] == "noop"

    count = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "policy", KnowledgeChunk.source_id == policy.id)
        .count()
    )
    assert count == 0


# 13. Full reconciliation correctly removes stale managed chunks without deleting unrelated data.
def test_full_reconciliation_cleans_stale_chunks_and_preserves_unrelated(db_session, admin_user):
    # 1. Approved policy (eligible)
    p_active = Policy(
        id=uuid.uuid4(),
        title="Active Policy",
        description="Active policy desc",
        category=PolicyCategory.HEALTHCARE,
        department="Health",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(p_active)

    # 2. Archived policy (ineligible)
    p_archived = Policy(
        id=uuid.uuid4(),
        title="Archived Policy",
        description="Archived desc",
        category=PolicyCategory.HEALTHCARE,
        department="Health",
        status=PolicyStatus.ARCHIVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(p_archived)

    # 3. Active scheme (eligible)
    s_active = Scheme(
        id=uuid.uuid4(),
        policy_id=p_active.id,
        title="Active Scheme",
        description="Active scheme desc",
        category=SchemeCategory.HEALTHCARE,
        department="Health",
        status=SchemeStatus.ACTIVE,
        created_by=admin_user.id,
    )
    db_session.add(s_active)

    # 4. Inactive scheme (ineligible)
    s_rejected = Scheme(
        id=uuid.uuid4(),
        policy_id=p_active.id,
        title="Rejected Scheme",
        description="Rejected desc",
        category=SchemeCategory.HEALTHCARE,
        department="Health",
        status=SchemeStatus.REJECTED,
        created_by=admin_user.id,
    )
    db_session.add(s_rejected)

    # Insert orphaned chunks for the ineligible records
    stale_p_chunk = KnowledgeChunk(
        source_type="policy",
        source_id=p_archived.id,
        title="Archived Policy",
        content="Old content",
        chunk_index=0,
        embedding=[0.2] * 384,
    )
    stale_s_chunk = KnowledgeChunk(
        source_type="scheme",
        source_id=s_rejected.id,
        title="Rejected Scheme",
        content="Old content",
        chunk_index=0,
        embedding=[0.2] * 384,
    )
    # Insert an unrelated chunk (e.g., FAQ)
    faq_id = uuid.uuid4()
    unrelated_chunk = KnowledgeChunk(
        source_type="faq",
        source_id=faq_id,
        title="How to register",
        content="FAQ content about registration process",
        chunk_index=0,
        embedding=[0.3] * 384,
    )
    db_session.add_all([stale_p_chunk, stale_s_chunk, unrelated_chunk])
    db_session.commit()

    # Run full reconciliation
    stats = ingest_knowledge_base(db_session, remove_stale=True)

    assert stats["policies"] == 1
    assert stats["schemes"] == 1
    assert stats["removed_policies"] == 1
    assert stats["removed_schemes"] == 1

    # Verify stale chunks were removed
    assert (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_id == p_archived.id)
        .first()
        is None
    )
    assert (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_id == s_rejected.id)
        .first()
        is None
    )

    # Verify active chunks exist
    assert (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_id == p_active.id)
        .first()
        is not None
    )
    assert (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_id == s_active.id)
        .first()
        is not None
    )

    # Verify unrelated chunk was PRESERVED
    faq_chunk = (
        db_session.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_type == "faq", KnowledgeChunk.source_id == faq_id)
        .first()
    )
    assert faq_chunk is not None
    assert faq_chunk.title == "How to register"


# 14. Existing manual ingestion still works.
def test_existing_manual_ingestion_still_works(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Manual Ingestion Policy",
        description="Policy for manual test",
        category=PolicyCategory.FINANCE,
        department="Finance",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    scheme = Scheme(
        id=uuid.uuid4(),
        policy_id=policy.id,
        title="Manual Ingestion Scheme",
        description="Scheme for manual test",
        category=SchemeCategory.BUSINESS_SUPPORT,
        department="Finance",
        status=SchemeStatus.ACTIVE,
        created_by=admin_user.id,
    )
    db_session.add_all([policy, scheme])
    db_session.commit()

    result = ingest_knowledge_base(db_session)
    assert "policies" in result
    assert "schemes" in result
    assert "total" in result
    assert result["policies"] == 1
    assert result["schemes"] == 1
    assert result["total"] == 2


# 15. Existing Helpdesk retrieval and response behavior remain unchanged.
def test_helpdesk_retrieval_and_response_behavior_unchanged(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="PM Kisan Samman Nidhi",
        description="Direct income support of 6000 rupees per year to farmers.",
        category=PolicyCategory.AGRICULTURE,
        department="Agriculture",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    sync_policy_knowledge(db_session, policy.id)

    # Test retrieval with mocked distance and LLM
    with patch("backend.app.ai.llm_client.LLMClient.generate_text", return_value="Farmers receive 6000 rupees per year."):
        # We query the chunk and mock retrieve_relevant_chunks
        chunk = db_session.query(KnowledgeChunk).filter(KnowledgeChunk.source_id == policy.id).first()
        with patch(
            "backend.app.ai.helpdesk_service.retrieve_relevant_chunks",
            return_value=[(chunk, 0.88)],
        ):
            resp = answer_helpdesk_question(db_session, "How much support do farmers get?")
            assert resp["answer"] == "Farmers receive 6000 rupees per year."
            assert len(resp["sources"]) == 1
            assert resp["sources"][0]["title"] == "PM Kisan Samman Nidhi"
            assert resp["sources"][0]["similarity"] == 0.88


# 16. Service-layer approval automatically triggers indexing
# (commit -> schedule -> chunk), not just the sync function in isolation.
def test_service_approval_automatically_indexes_policy(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Approved Through Service",
        description="Automatic trigger coverage.",
        category=PolicyCategory.HEALTHCARE,
        department="Health",
        status=PolicyStatus.PENDING_APPROVAL,
        uploaded_by=admin_user.id,
    )
    db_session.add(policy)
    db_session.commit()

    # Force the real service -> schedule -> sync chain to run synchronously.
    # The sync gets its OWN session on the same engine (as in production),
    # so its commit/close never expires the objects under test.
    SyncSession = sessionmaker(bind=db_session.get_bind())
    with patch(
        "backend.app.ai.sync_service.SYNC_IN_BACKGROUND", False
    ), patch(
        "backend.app.ai.sync_service.SessionLocal", return_value=SyncSession()
    ):
        approved = approve_policy(db_session, policy.id, admin_user)

    assert approved.status == PolicyStatus.APPROVED

    chunk = (
        db_session.query(KnowledgeChunk)
        .filter(
            KnowledgeChunk.source_type == "policy",
            KnowledgeChunk.source_id == policy.id,
        )
        .one()
    )
    assert chunk.title == "Approved Through Service"
    assert "Approved Through Service" in chunk.content
    assert len(chunk.embedding) == 384

    record = get_sync_status("policy", policy.id)
    assert record is not None
    assert record.status == SyncStatus.SUCCESS
    assert record.action == SyncAction.INDEXED


# 17. Service-layer archiving automatically removes chunks
# (eligible -> ineligible through the real workflow).
def test_service_archive_automatically_removes_chunks(db_session, official_user):
    profile = GovernmentOfficialProfile(
        user_id=official_user.id,
        department="Health",
        designation="Secretary",
        official_id="GOV-1001",
        state="Maharashtra",
    )
    policy = Policy(
        id=uuid.uuid4(),
        title="Archived Through Service",
        description="Automatic removal coverage.",
        category=PolicyCategory.HEALTHCARE,
        department="Health",
        status=PolicyStatus.APPROVED,
        uploaded_by=official_user.id,
    )
    db_session.add_all([profile, policy])
    db_session.commit()

    sync_policy_knowledge(db_session, policy.id)
    assert (
        db_session.query(KnowledgeChunk)
        .filter(
            KnowledgeChunk.source_type == "policy",
            KnowledgeChunk.source_id == policy.id,
        )
        .count()
        == 1
    )

    SyncSession = sessionmaker(bind=db_session.get_bind())
    with patch(
        "backend.app.ai.sync_service.SYNC_IN_BACKGROUND", False
    ), patch(
        "backend.app.ai.sync_service.SessionLocal", return_value=SyncSession()
    ):
        archived = archive_policy(db_session, policy.id, official_user)

    assert archived.status == PolicyStatus.ARCHIVED
    assert (
        db_session.query(KnowledgeChunk)
        .filter(
            KnowledgeChunk.source_type == "policy",
            KnowledgeChunk.source_id == policy.id,
        )
        .count()
        == 0
    )

    record = get_sync_status("policy", policy.id)
    assert record is not None
    assert record.status == SyncStatus.SUCCESS
    assert record.action == SyncAction.REMOVED


# 18. Scheme service approval automatically triggers indexing.
def test_service_scheme_approval_automatically_indexes(db_session, admin_user):
    policy = Policy(
        id=uuid.uuid4(),
        title="Scheme Trigger Parent Policy",
        description="Parent policy for scheme trigger coverage.",
        category=PolicyCategory.EDUCATION,
        department="Education",
        status=PolicyStatus.APPROVED,
        uploaded_by=admin_user.id,
    )
    scheme = Scheme(
        id=uuid.uuid4(),
        policy_id=policy.id,
        title="Activated Through Service",
        description="Scheme approved through the service layer.",
        category=SchemeCategory.SCHOLARSHIPS,
        department="Education",
        status=SchemeStatus.PENDING_APPROVAL,
        benefits=["Tuition fee waiver"],
        created_by=admin_user.id,
    )
    db_session.add_all([policy, scheme])
    db_session.commit()

    SyncSession = sessionmaker(bind=db_session.get_bind())
    with patch(
        "backend.app.ai.sync_service.SYNC_IN_BACKGROUND", False
    ), patch(
        "backend.app.ai.sync_service.SessionLocal", return_value=SyncSession()
    ):
        activated = approve_scheme(db_session, scheme.id, admin_user)

    assert activated.status == SchemeStatus.ACTIVE

    chunk = (
        db_session.query(KnowledgeChunk)
        .filter(
            KnowledgeChunk.source_type == "scheme",
            KnowledgeChunk.source_id == scheme.id,
        )
        .one()
    )
    assert chunk.title == "Activated Through Service"
    assert "Tuition fee waiver" in chunk.content
    assert len(chunk.embedding) == 384

    record = get_sync_status("scheme", scheme.id)
    assert record is not None
    assert record.status == SyncStatus.SUCCESS
    assert record.action == SyncAction.INDEXED


# 19. The background thread pool (the production default path) indexes a
# record end to end: schedule -> worker thread -> commit -> registry.
def test_background_schedule_indexes_record():
    clear_sync_registry()

    # StaticPool + check_same_thread=False lets the worker thread share one
    # in-memory SQLite connection with the main thread.
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "gen_random_uuid", 0, lambda: str(uuid.uuid4())
        )

    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()

    try:
        user = User(
            id=uuid.uuid4(),
            email="background@policygpt.gov",
            password_hash="fakehash",
            full_name="Background Admin",
            role=UserRole.ADMINISTRATOR,
            email_verified=True,
        )
        policy = Policy(
            id=uuid.uuid4(),
            title="Background Sync Policy",
            description="Indexed from the worker thread.",
            category=PolicyCategory.FINANCE,
            department="Finance",
            status=PolicyStatus.APPROVED,
            uploaded_by=user.id,
        )
        db.add_all([user, policy])
        db.commit()
        expected_updated_at = policy.updated_at
        # Release the refresh transaction so the worker session starts clean
        # on the shared StaticPool connection.
        db.commit()

        with patch(
            "backend.app.ai.sync_service.SessionLocal",
            return_value=TestingSession(),
        ):
            schedule_policy_sync(
                policy.id,
                expected_updated_at=expected_updated_at,
                background=True,
            )
            wait_for_sync_tasks(timeout=15)

        record = get_sync_status("policy", policy.id)
        assert record is not None
        assert record.status == SyncStatus.SUCCESS, record.error
        assert record.action == SyncAction.INDEXED

        chunk = (
            db.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.source_type == "policy",
                KnowledgeChunk.source_id == policy.id,
            )
            .one()
        )
        assert len(chunk.embedding) == 384
    finally:
        db.close()
        clear_sync_registry()

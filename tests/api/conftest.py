"""Shared test harness for the tests/api package.

Drives real HTTP requests through the FastAPI app (TestClient) against an
in-memory SQLite database with the Postgres-only column types compiled to
SQLite equivalents (same trick as tests/ai).
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapper, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth.dependencies import get_current_user
from backend.app.db.database import Base, get_db
from backend.app.main import app
from backend.app.models.government_official_profile import (
    GovernmentOfficialProfile,
)
from backend.app.models.policy import Policy, PolicyCategory, PolicyStatus
from backend.app.models.scheme import Scheme, SchemeCategory, SchemeStatus
from backend.app.models.user import User, UserRole
from backend.app.models.user_profile import UserProfile


# SQLite stand-ins for the Postgres-only column types
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@compiles(Vector, "sqlite")
def _compile_vector_sqlite(type_, compiler, **kw):
    return "JSON"


@event.listens_for(Mapper, "before_insert")
def _assign_server_default_uuid_pk(mapper, connection, target):
    """Emulate Postgres server-default primary keys on SQLite.

    On Postgres, INSERT...RETURNING fills in `gen_random_uuid()` ids, which
    production code relies on via `db.refresh(obj)` after commit. SQLite
    applies the column default but never reports it back to the ORM, so any
    create endpoint would crash in tests. Assign the id client-side here —
    test harness only, no production code involved.
    """
    for column in mapper.primary_key:
        if column.name == "id" and getattr(target, "id", None) is None:
            target.id = uuid.uuid4()


@pytest.fixture(autouse=True)
def no_background_sync():
    """Never spawn knowledge-sync worker threads during request tests."""
    with patch(
        "backend.app.policies.service.schedule_policy_sync"
    ), patch(
        "backend.app.schemes.service.schedule_scheme_sync"
    ):
        yield


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _register_functions(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "gen_random_uuid", 0, lambda: str(uuid.uuid4())
        )

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def seed(session_factory):
    """Commit a record and return it (visible to every request session)."""

    def _add(obj):
        db = session_factory()
        try:
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return obj
        finally:
            db.close()

    return _add


@pytest.fixture()
def api(session_factory):
    """TestClient wired to the SQLite DB with a settable current user.

    raise_server_exceptions=False so server-side failures surface as real
    500 responses, exactly like production.
    """
    current: dict = {}

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_current_user(db: Session = Depends(get_db)):
        return db.get(User, current["user_id"])

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(
            client=client,
            login=lambda user: current.__setitem__("user_id", user.id),
        )

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def citizen(seed):
    return seed(
        User(
            id=uuid.uuid4(),
            email=f"citizen-{uuid.uuid4().hex[:8]}@example.gov",
            password_hash="x",
            full_name="Test Citizen",
            role=UserRole.CITIZEN,
            email_verified=True,
            is_active=True,
        )
    )


@pytest.fixture()
def other_citizen(seed):
    return seed(
        User(
            id=uuid.uuid4(),
            email=f"citizen2-{uuid.uuid4().hex[:8]}@example.gov",
            password_hash="x",
            full_name="Second Citizen",
            role=UserRole.CITIZEN,
            email_verified=True,
            is_active=True,
        )
    )


@pytest.fixture()
def official(seed):
    user = seed(
        User(
            id=uuid.uuid4(),
            email=f"official-{uuid.uuid4().hex[:8]}@example.gov",
            password_hash="x",
            full_name="Test Official",
            role=UserRole.GOVERNMENT_OFFICIAL,
            email_verified=True,
            is_active=True,
        )
    )
    seed(
        GovernmentOfficialProfile(
            user_id=user.id,
            department="Health",
            designation="Director",
            official_id="GOV-1234",
            state="Karnataka",
        )
    )
    return user


def _policy(**overrides):
    fields = dict(
        id=uuid.uuid4(),
        title="Original Policy",
        description="Original description",
        category=PolicyCategory.HEALTHCARE,
        department="Health",
        ministry="Health",
        status=PolicyStatus.DRAFT,
    )
    fields.update(overrides)
    return Policy(**fields)


def _scheme(**overrides):
    fields = dict(
        id=uuid.uuid4(),
        title="Original Scheme",
        description="Original description",
        category=SchemeCategory.HEALTHCARE,
        department="Health",
        status=SchemeStatus.DRAFT,
    )
    fields.update(overrides)
    return Scheme(**fields)


@pytest.fixture()
def draft_policy(seed, official):
    return seed(_policy(uploaded_by=official.id))


@pytest.fixture()
def approved_policy(seed, official):
    return seed(_policy(uploaded_by=official.id, status=PolicyStatus.APPROVED))


@pytest.fixture()
def draft_scheme(seed, official, draft_policy):
    return seed(
        _scheme(
            policy_id=draft_policy.id,
            created_by=official.id,
        )
    )

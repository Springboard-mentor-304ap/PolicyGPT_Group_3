"""Operational hardening bugs (items 3, 4, 5, 6).

Item 3: CORS allows only the configured origins, never a wildcard.
Item 4: generated report files are deleted after REPORT_RETENTION_DAYS and
        the download endpoint answers 410 Gone for an expired report.
Item 5: Excel column widths are computed across every table on the sheet,
        not per table (the last table used to win).
Item 6: /health checks the database connection; seed scripts refuse to run
        when ENVIRONMENT=production.
"""

import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import get_db
from backend.app.main import app
from backend.app.models.report import Report, ReportFormat, ReportType
from backend.app.models.user import User, UserRole
from backend.app.reports.generators.excel import generate_excel_report
from backend.app.reports.schemas import (
    ReportContent,
    ReportSection,
    ReportTable,
)
from backend.app.reports.service import cleanup_expired_reports

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

MIN_COLUMN_WIDTH = 10
MAX_COLUMN_WIDTH = 60


@pytest.fixture()
def report_file_dir(tmp_path, monkeypatch):
    """Point the reports directory at a per-test temp dir.

    cleanup_expired_reports and the download endpoint resolve files through
    the service module's REPORTS_DIRECTORY constant, so patching it keeps
    tests from touching (or deleting) real generated files.
    """
    monkeypatch.setattr(
        "backend.app.reports.service.REPORTS_DIRECTORY", tmp_path
    )
    return tmp_path


@pytest.fixture()
def retention_db():
    """One SQLite engine shared by the cleanup and the request sessions.

    The cleanup runs against its own session in the maintenance loop, and the
    download endpoint must see the rows it marked, so both sides are wired to
    this engine instead of the request-scoped fixture database.
    """
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    from backend.app.db.database import Base

    Base.metadata.create_all(engine)

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    session = factory()
    yield session
    session.close()
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


def _seed_user(db, role):
    user = User(
        id=uuid.uuid4(),
        email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.gov",
        password_hash="x",
        full_name="Test User",
        role=role,
        email_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_report(db, generated_at, report_format=ReportFormat.PDF):
    report = Report(
        id=uuid.uuid4(),
        generated_by=uuid.uuid4(),
        report_type=ReportType.POLICY,
        format=report_format,
        filters_used={},
        file_url="/api/reports/x/download",
        generated_at=generated_at,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


# ─── Item 3: CORS reflects only the configured origins ──────────────────────
def test_cors_allows_configured_origin_and_rejects_others(api):
    # The Angular dev server is the default allowed origin.
    preflight = api.client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:4200",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert preflight.status_code == 200
    assert (
        preflight.headers["access-control-allow-origin"]
        == "http://localhost:4200"
    )
    assert preflight.headers["access-control-allow-credentials"] == "true"

    # A normal (non-preflight) response carries the header too.
    response = api.client.get(
        "/health", headers={"Origin": "http://localhost:4200"}
    )
    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:4200"
    )

    # An unlisted origin gets no CORS grant, and never an echo of "*".
    foreign = api.client.options(
        "/api/auth/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in foreign.headers


# ─── Item 6: /health checks the database ────────────────────────────────────
def test_health_endpoint_reports_database_status(api):
    response = api.client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_endpoint_returns_503_when_database_is_unreachable(tmp_path):
    # A file-backed engine whose directory does not exist cannot connect.
    unreachable = create_engine(
        f"sqlite:///{tmp_path / 'missing-dir' / 'db.sqlite'}"
    )

    def override_broken_db():
        session = sessionmaker(bind=unreachable)()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_broken_db

    with TestClient(app, raise_server_exceptions=False) as client:
        try:
            response = client.get("/health")
        finally:
            app.dependency_overrides.pop(get_db, None)

    unreachable.dispose()

    assert response.status_code == 503
    assert "Database connection" in response.json()["detail"]


# ─── Item 4: report retention cleanup + 410 Gone ────────────────────────────
def test_cleanup_deletes_expired_files_and_download_returns_410(
    retention_db, report_file_dir,
):
    now = datetime.now(timezone.utc)
    expired = _seed_report(retention_db, generated_at=now - timedelta(days=40))
    fresh = _seed_report(retention_db, generated_at=now - timedelta(days=1))
    admin = _seed_user(retention_db, UserRole.ADMINISTRATOR)

    expired_file = report_file_dir / f"{expired.id}.pdf"
    fresh_file = report_file_dir / f"{fresh.id}.pdf"
    expired_file.write_bytes(b"%PDF-1.4 expired")
    fresh_file.write_bytes(b"%PDF-1.4 fresh")

    with TestClient(app, raise_server_exceptions=False) as client:
        # Normal path: nothing expires before the retention window elapses.
        assert cleanup_expired_reports(retention_db, retention_days=60) == 0
        assert expired_file.exists() and fresh_file.exists()

        # Bug: the file used to survive forever and the row was never marked.
        removed = cleanup_expired_reports(retention_db)
        assert removed == 1
        assert not expired_file.exists()
        assert fresh_file.exists()

        retention_db.expire_all()
        assert expired.file_deleted_at is not None
        assert fresh.file_deleted_at is None

        # A second sweep is idempotent: nothing left to expire.
        assert cleanup_expired_reports(retention_db) == 0

        headers = {"Authorization": "Bearer test"}

        # Wire the request's current user to the seeded admin.
        from backend.app.auth.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: admin

        try:
            # Bug: a deleted file used to answer 404; expiry is a 410 Gone.
            gone = client.get(
                f"/api/reports/{expired.id}/download", headers=headers
            )
            assert gone.status_code == 410
            assert "expired" in gone.json()["detail"].lower()

            # The row is still listed; only the file is gone.
            listing = client.get("/api/reports", headers=headers)
            assert listing.status_code == 200
            listed_ids = {row["id"] for row in listing.json()}
            assert str(expired.id) in listed_ids
            assert str(fresh.id) in listed_ids

            # Normal path: a fresh report still downloads.
            ok = client.get(
                f"/api/reports/{fresh.id}/download", headers=headers
            )
            assert ok.status_code == 200
            assert ok.content == b"%PDF-1.4 fresh"
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ─── Item 5: Excel widths span every table on the sheet ─────────────────────
def test_excel_column_widths_cover_all_tables_on_a_sheet(tmp_path):
    wide_column = "A very wide header column"
    content = ReportContent(
        title="Policy Report",
        report_type=ReportType.POLICY,
        format=ReportFormat.EXCEL,
        generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        generated_by="Test Admin",
        filters={},
        summary=[],
        sections=[
            ReportSection(
                title="Two Tables",
                tables=[
                    ReportTable(
                        title="Short Table",
                        columns=["A", "B"],
                        rows=[[1, 2]],
                    ),
                    ReportTable(
                        title="Wide Table",
                        columns=[wide_column, "B"],
                        rows=[["x" * 80, "y"]],
                    ),
                ],
            )
        ],
    )

    output_path = tmp_path / "report.xlsx"
    generate_excel_report(content, output_path)

    sheet = load_workbook(str(output_path)).active

    width_a = sheet.column_dimensions["A"].width
    width_b = sheet.column_dimensions["B"].width

    # Bug: the last table on the sheet set the widths, so the first table's
    # wide cells were clipped. Column A now takes the widest need (80 chars,
    # capped) rather than the 1-char width of the short table.
    assert width_a == min(80 + 2, MAX_COLUMN_WIDTH)
    assert width_a > len(wide_column) + 2

    # Column B is only used for short values, but still reaches the floor.
    assert width_b == MIN_COLUMN_WIDTH

    # The header block is still written above the tables.
    assert sheet["A1"].value == "PolicyGPT"


# ─── Item 6: seed scripts refuse to run in production ───────────────────────
def _production_env(tmp_path=None):
    env = dict(os.environ)
    env["ENVIRONMENT"] = "production"
    env["JWT_SECRET_KEY"] = env.get("JWT_SECRET_KEY", "test-secret")
    env["SEED_SUPER_ADMIN_PASSWORD"] = "ChangeMe@12345"
    env["SEED_ADMIN_PASSWORD"] = "ChangeMe@12345"

    if tmp_path is not None:
        env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'seed.sqlite'}"

    return env


@pytest.mark.parametrize(
    "module",
    [
        "backend.app.seed_super_admin",
        "backend.app.seed_admins",
        "backend.seed_realistic_data",
    ],
)
def test_seed_scripts_refuse_to_run_in_production(module, tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", module],
        cwd=PROJECT_ROOT,
        env=_production_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    combined = (result.stdout + result.stderr).lower()
    assert "production" in combined

    # The guard fires before any connection, so no database file appears.
    assert not (tmp_path / "seed.sqlite").exists()

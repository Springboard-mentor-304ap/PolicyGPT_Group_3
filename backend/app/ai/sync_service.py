"""Automatic knowledge-base synchronization for policies and schemes.

After a policy/scheme service transaction commits, it calls
``schedule_policy_sync`` / ``schedule_scheme_sync``, which submit a small job
that reloads the authoritative record and upserts or removes its knowledge
chunks. Jobs run on a process-local thread pool (``SYNC_WORKER_THREADS``,
default 2) so embedding generation and chunk writes happen outside the
request's transaction.

The project has no task queue — see the in-process deadline-reminder sweep in
``backend.app.main`` — so, like that sweep, synchronization is deliberately
in-process rather than Celery-based. Reliability limitations:

* Jobs and the outcome registry (``get_sync_status``, ``get_failed_syncs``)
live in process memory: a restart drops jobs that were scheduled but not yet
finished and resets the registry. Structured logs survive; after a crash or
deploy run the reconciliation command
``python -m backend.app.ai.knowledge_ingestion`` to bring the knowledge base
back in line with the database.
* A single-process pool has no cross-instance coordination: multiple API
workers can race on the same record. Per-record locks plus the freshness
checks keep the final state correct, but duplicate work is possible.
* Failed jobs retry up to ``SYNC_MAX_RETRIES`` times with a short exponential
backoff, then stay marked ``failed`` in the registry and in logs until a
manual ``retry_sync`` or full reconciliation.

Every outcome is logged with source type, source id, action
(indexed/updated/removed/noop), status and failure reason. No secrets are
logged.
"""

import logging
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.database import SessionLocal

logger = logging.getLogger(__name__)

# Configuration
SYNC_WORKER_THREADS = int(os.getenv("SYNC_WORKER_THREADS", "2"))
SYNC_MAX_RETRIES = int(os.getenv("SYNC_MAX_RETRIES", "3"))
SYNC_IN_BACKGROUND = os.getenv("SYNC_IN_BACKGROUND", "true").lower() in ("true", "1")


class SyncStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED_STALE = "skipped_stale"


class SyncAction(str, Enum):
    INDEXED = "indexed"
    UPDATED = "updated"
    REMOVED = "removed"
    NOOP = "noop"


@dataclass
class SyncRecord:
    source_type: str
    source_id: UUID
    status: SyncStatus
    action: SyncAction
    error: str | None
    timestamp: datetime
    attempts: int = 1


# In-memory synchronization registry and lock management
_locks_guard = threading.Lock()
_record_locks: dict[tuple[str, UUID], threading.Lock] = {}

_registry_guard = threading.Lock()
_sync_registry: dict[tuple[str, UUID], SyncRecord] = {}

_executor_guard = threading.Lock()
_executor: ThreadPoolExecutor | None = None
_active_futures: set[Future] = set()


def _get_record_lock(source_type: str, source_id: UUID) -> threading.Lock:
    key = (source_type, source_id)
    with _locks_guard:
        if key not in _record_locks:
            _record_locks[key] = threading.Lock()
        return _record_locks[key]


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_guard:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=SYNC_WORKER_THREADS,
                thread_name_prefix="kb-sync-worker",
            )
        return _executor


def shutdown_sync_executor(wait: bool = True) -> None:
    """Shut down the background synchronization executor."""
    global _executor
    with _executor_guard:
        if _executor is not None:
            _executor.shutdown(wait=wait)
            _executor = None


def wait_for_sync_tasks(timeout: float = 10.0) -> None:
    """Wait for all currently scheduled background sync tasks to finish."""
    with _executor_guard:
        futures = list(_active_futures)

    deadline = datetime.now(timezone.utc).timestamp() + timeout
    for fut in futures:
        remaining = max(0.0, deadline - datetime.now(timezone.utc).timestamp())
        try:
            fut.result(timeout=remaining)
        except Exception:
            pass


def get_sync_status(source_type: str, source_id: UUID) -> SyncRecord | None:
    """Inspect the recorded outcome and freshness for a source record."""
    with _registry_guard:
        return _sync_registry.get((source_type, source_id))


def get_failed_syncs() -> list[SyncRecord]:
    """Return all source records whose last synchronization failed."""
    with _registry_guard:
        return [
            rec for rec in _sync_registry.values()
            if rec.status == SyncStatus.FAILED
        ]


def clear_sync_registry() -> None:
    """Reset the sync registry and per-record locks (primarily for testing)."""
    with _registry_guard:
        _sync_registry.clear()
    with _locks_guard:
        _record_locks.clear()


def sync_source_record(
    source_type: str,
    source_id: UUID,
    db: Session | None = None,
    expected_updated_at: datetime | None = None,
) -> dict:
    """Synchronize a single policy or scheme record into the knowledge base.

    Serialized per (source_type, source_id) to eliminate concurrent races.
    Loads the current authoritative state from the database.
    """
    from backend.app.ai.knowledge_ingestion import (
        sync_policy_knowledge,
        sync_scheme_knowledge,
    )

    lock = _get_record_lock(source_type, source_id)
    with lock:
        should_close_db = False
        active_db = db

        if active_db is None:
            active_db = SessionLocal()
            should_close_db = True

        try:
            if source_type == "policy":
                result = sync_policy_knowledge(
                    active_db,
                    source_id,
                    expected_updated_at=expected_updated_at,
                )
            elif source_type == "scheme":
                result = sync_scheme_knowledge(
                    active_db,
                    source_id,
                    expected_updated_at=expected_updated_at,
                )
            else:
                raise ValueError(f"Unknown source_type: {source_type}")

            status_str = result.get("status", SyncStatus.SUCCESS.value)
            action_str = result.get("action", SyncAction.NOOP.value)

            sync_status = (
                SyncStatus.SKIPPED_STALE
                if status_str == "skipped_stale"
                else SyncStatus.SUCCESS
            )
            sync_action = SyncAction(action_str)

            with _registry_guard:
                prev = _sync_registry.get((source_type, source_id))
                attempts = (prev.attempts + 1) if prev else 1
                _sync_registry[(source_type, source_id)] = SyncRecord(
                    source_type=source_type,
                    source_id=source_id,
                    status=sync_status,
                    action=sync_action,
                    error=None,
                    timestamp=datetime.now(timezone.utc),
                    attempts=attempts,
                )

            logger.info(
                "Knowledge base sync completed: source_type=%s source_id=%s action=%s status=%s details=%s",
                source_type,
                source_id,
                sync_action.value,
                sync_status.value,
                result.get("details", ""),
            )
            return result

        except Exception as exc:
            if active_db is not None:
                try:
                    active_db.rollback()
                except Exception:
                    pass

            with _registry_guard:
                prev = _sync_registry.get((source_type, source_id))
                attempts = (prev.attempts + 1) if prev else 1
                _sync_registry[(source_type, source_id)] = SyncRecord(
                    source_type=source_type,
                    source_id=source_id,
                    status=SyncStatus.FAILED,
                    action=SyncAction.NOOP,
                    error=str(exc),
                    timestamp=datetime.now(timezone.utc),
                    attempts=attempts,
                )

            logger.error(
                "Knowledge base sync failed: source_type=%s source_id=%s error=%s",
                source_type,
                source_id,
                exc,
                exc_info=True,
            )
            raise
        finally:
            if should_close_db and active_db is not None:
                active_db.close()


def _background_worker(
    source_type: str,
    source_id: UUID,
    expected_updated_at: datetime | None,
    retry_count: int = 0,
) -> dict:
    try:
        return sync_source_record(
            source_type=source_type,
            source_id=source_id,
            db=None,
            expected_updated_at=expected_updated_at,
        )
    except Exception as exc:
        if retry_count < SYNC_MAX_RETRIES:
            # Short exponential backoff so a transient DB or embedding hiccup
            # does not burn all attempts in the same instant.
            time.sleep(0.5 * (2 ** retry_count))
            logger.warning(
                "Retrying failed knowledge sync for %s %s (attempt %d of %d)",
                source_type,
                source_id,
                retry_count + 1,
                SYNC_MAX_RETRIES,
            )
            return _background_worker(
                source_type=source_type,
                source_id=source_id,
                expected_updated_at=expected_updated_at,
                retry_count=retry_count + 1,
            )
        return {
            "source_type": source_type,
            "source_id": source_id,
            "status": SyncStatus.FAILED.value,
            "action": SyncAction.NOOP.value,
            "error": str(exc),
        }


def schedule_sync(
    source_type: str,
    source_id: UUID,
    expected_updated_at: datetime | None = None,
    background: bool | None = None,
    db: Session | None = None,
) -> Future | dict:
    """Schedule synchronization for a policy or scheme.

    If background is True (or SYNC_IN_BACKGROUND by default), runs outside the
    calling transaction using the thread pool; a caller-provided session is
    never handed to another thread, so the worker always opens its own session.
    If background is False, executes synchronously on the caller's session
    (when one is provided).
    """
    run_in_background = SYNC_IN_BACKGROUND if background is None else background

    if not run_in_background:
        return sync_source_record(
            source_type=source_type,
            source_id=source_id,
            db=db,
            expected_updated_at=expected_updated_at,
        )

    executor = _get_executor()
    future = executor.submit(
        _background_worker,
        source_type=source_type,
        source_id=source_id,
        expected_updated_at=expected_updated_at,
    )

    with _executor_guard:
        _active_futures.add(future)

    future.add_done_callback(
        lambda f: _active_futures.discard(f) if f in _active_futures else None
    )
    return future


def schedule_policy_sync(
    policy_id: UUID,
    expected_updated_at: datetime | None = None,
    background: bool | None = None,
    db: Session | None = None,
) -> Future | dict:
    """Convenience helper to schedule synchronization for a policy."""
    return schedule_sync(
        source_type="policy",
        source_id=policy_id,
        expected_updated_at=expected_updated_at,
        background=background,
        db=db,
    )


def schedule_scheme_sync(
    scheme_id: UUID,
    expected_updated_at: datetime | None = None,
    background: bool | None = None,
    db: Session | None = None,
) -> Future | dict:
    """Convenience helper to schedule synchronization for a scheme."""
    return schedule_sync(
        source_type="scheme",
        source_id=scheme_id,
        expected_updated_at=expected_updated_at,
        background=background,
        db=db,
    )


def retry_sync(
    source_type: str,
    source_id: UUID,
    db: Session | None = None,
    background: bool | None = None,
) -> Future | dict:
    """Retry synchronization for a previously failed or unindexed record."""
    logger.info("Retrying knowledge sync for %s id=%s", source_type, source_id)
    return schedule_sync(
        source_type=source_type,
        source_id=source_id,
        expected_updated_at=None,
        background=background,
        db=db,
    )


def retry_failed_syncs(
    db: Session | None = None,
    background: bool | None = None,
) -> list[dict]:
    """Retry synchronization for all records currently recorded as failed."""
    failed = get_failed_syncs()
    results = []
    for record in failed:
        retry_sync(
            source_type=record.source_type,
            source_id=record.source_id,
            db=db,
            background=background,
        )
        results.append({
            "source_type": record.source_type,
            "source_id": record.source_id,
            "scheduled": True,
        })
    return results

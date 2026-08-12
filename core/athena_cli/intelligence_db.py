"""Shared local persistence for Athena's operational intelligence layer.

The database is intentionally local and dependency-free.  It is a coordination
store, not conversation state: existing session, memory, Kanban, and checkpoint
databases remain the source of truth for their respective domains.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from athena_constants import get_athena_home


_SCHEMA_LOCK = threading.RLock()
_READY_PATHS: set[str] = set()


def database_path() -> Path:
    return get_athena_home() / "operations" / "athena-operations.db"


def _connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or database_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def ensure_schema(path: Path | None = None) -> None:
    target = path or database_path()
    key = str(target.resolve())
    if key in _READY_PATHS:
        return
    with _SCHEMA_LOCK:
        if key in _READY_PATHS:
            return
        conn = _connect(target)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS trace_runs (
                    id TEXT PRIMARY KEY,
                    run_key TEXT,
                    session_id TEXT NOT NULL DEFAULT '',
                    task_id TEXT NOT NULL DEFAULT '',
                    parent_session_id TEXT NOT NULL DEFAULT '',
                    platform TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    provider TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'running',
                    started_at REAL NOT NULL,
                    ended_at REAL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
                    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost_usd REAL NOT NULL DEFAULT 0,
                    model_calls INTEGER NOT NULL DEFAULT 0,
                    tool_calls INTEGER NOT NULL DEFAULT 0,
                    retries INTEGER NOT NULL DEFAULT 0,
                    error_count INTEGER NOT NULL DEFAULT 0,
                    summary TEXT NOT NULL DEFAULT '',
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_trace_runs_started
                    ON trace_runs(started_at DESC);
                CREATE INDEX IF NOT EXISTS idx_trace_runs_session
                    ON trace_runs(session_id, task_id, started_at DESC);
                CREATE INDEX IF NOT EXISTS idx_trace_runs_key
                    ON trace_runs(run_key, started_at DESC);

                CREATE TABLE IF NOT EXISTS trace_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES trace_runs(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    span_key TEXT NOT NULL DEFAULT '',
                    parent_span_key TEXT NOT NULL DEFAULT '',
                    occurred_at REAL NOT NULL,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT '',
                    payload TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_trace_events_run
                    ON trace_events(run_id, occurred_at, id);

                CREATE TABLE IF NOT EXISTS review_items (
                    id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'ready',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(source_type, source_id)
                );
                CREATE INDEX IF NOT EXISTS idx_review_items_status
                    ON review_items(status, updated_at DESC);

                CREATE TABLE IF NOT EXISTS review_artifacts (
                    id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL REFERENCES review_items(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    media_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    sha256 TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_review_artifacts_item
                    ON review_artifacts(item_id, version DESC);

                CREATE TABLE IF NOT EXISTS route_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_kind TEXT NOT NULL,
                    model TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT '',
                    success INTEGER NOT NULL,
                    quality REAL NOT NULL DEFAULT 0,
                    latency_seconds REAL NOT NULL DEFAULT 0,
                    cost_usd REAL NOT NULL DEFAULT 0,
                    tool_success REAL NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_route_observations_lookup
                    ON route_observations(task_kind, model, provider, created_at DESC);

                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    baseline TEXT NOT NULL,
                    candidate TEXT NOT NULL,
                    traffic_percent REAL NOT NULL DEFAULT 5,
                    status TEXT NOT NULL DEFAULT 'draft',
                    min_samples INTEGER NOT NULL DEFAULT 20,
                    max_regression REAL NOT NULL DEFAULT 0.02,
                    baseline_runs INTEGER NOT NULL DEFAULT 0,
                    candidate_runs INTEGER NOT NULL DEFAULT 0,
                    baseline_score REAL NOT NULL DEFAULT 0,
                    candidate_score REAL NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS flow_definitions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    version INTEGER NOT NULL,
                    definition TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS flow_runs (
                    id TEXT PRIMARY KEY,
                    flow_id TEXT NOT NULL REFERENCES flow_definitions(id),
                    status TEXT NOT NULL DEFAULT 'pending',
                    input TEXT NOT NULL DEFAULT '{}',
                    output TEXT NOT NULL DEFAULT '{}',
                    error TEXT NOT NULL DEFAULT '',
                    parent_run_id TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_flow_runs_status
                    ON flow_runs(status, updated_at DESC);
                CREATE TABLE IF NOT EXISTS flow_step_runs (
                    run_id TEXT NOT NULL REFERENCES flow_runs(id) ON DELETE CASCADE,
                    step_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempt INTEGER NOT NULL DEFAULT 0,
                    started_at REAL,
                    ended_at REAL,
                    input TEXT NOT NULL DEFAULT '{}',
                    output TEXT NOT NULL DEFAULT '{}',
                    error TEXT NOT NULL DEFAULT '',
                    checkpoint TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY(run_id, step_id)
                );

                CREATE TABLE IF NOT EXISTS worker_nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    labels TEXT NOT NULL DEFAULT '[]',
                    capabilities TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'offline',
                    last_heartbeat REAL NOT NULL DEFAULT 0,
                    active_jobs INTEGER NOT NULL DEFAULT 0,
                    max_jobs INTEGER NOT NULL DEFAULT 1,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_worker_nodes_status
                    ON worker_nodes(status, last_heartbeat DESC);

                CREATE TABLE IF NOT EXISTS distributed_jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    requirements TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'queued',
                    priority INTEGER NOT NULL DEFAULT 0,
                    worker_id TEXT NOT NULL DEFAULT '',
                    lease_until REAL NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    result TEXT NOT NULL DEFAULT '{}',
                    error TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_distributed_jobs_queue
                    ON distributed_jobs(status, priority DESC, created_at);
                """
            )
            conn.commit()
            _READY_PATHS.add(key)
        finally:
            conn.close()


@contextmanager
def connection(*, write: bool = False) -> Iterator[sqlite3.Connection]:
    ensure_schema()
    conn = _connect()
    try:
        yield conn
        if write:
            conn.commit()
    except Exception:
        if write:
            conn.rollback()
        raise
    finally:
        conn.close()


def reset_schema_cache_for_tests() -> None:
    with _SCHEMA_LOCK:
        _READY_PATHS.clear()

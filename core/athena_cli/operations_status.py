"""Compact operational health summary for CLI and dashboard consumers."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from athena_constants import get_athena_home


def _safe(call: Callable[[], Any], fallback: Any) -> Any:
    try:
        return call()
    except Exception as exc:
        value = dict(fallback) if isinstance(fallback, dict) else fallback
        if isinstance(value, dict):
            value["error"] = str(exc)
        return value


def _memory() -> dict[str, Any]:
    path = get_athena_home() / "memories" / "athena_memory.db"
    if not path.is_file():
        return {"available": False, "active_memories": 0, "safe_archive_candidates": 0}
    from plugins.memory.athena.store import AthenaMemoryStore
    store = AthenaMemoryStore(str(path))
    try:
        status = store.status()
        review = store.review(limit=200)
        return {
            "available": True,
            **status,
            "stale_candidates": len(review["stale"]),
            "duplicate_candidates": len(review["duplicates"]),
            "safe_archive_candidates": len(review["safe_archive_ids"]),
        }
    finally:
        store.close()


def _kanban_evidence() -> dict[str, Any]:
    from athena_cli.kanban_db import kanban_db_path
    path = kanban_db_path()
    if not path.is_file():
        return {"completed_runs_checked": 0, "verified_runs": 0, "coverage": 0.0}
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        rows = conn.execute(
            "SELECT metadata FROM task_runs WHERE outcome = 'completed' ORDER BY ended_at DESC LIMIT 100"
        ).fetchall()
    finally:
        conn.close()
    verified = 0
    recorded = 0
    for (raw,) in rows:
        try:
            metadata = json.loads(raw or "{}")
        except json.JSONDecodeError:
            continue
        assessment = metadata.get("completion_assessment")
        if isinstance(assessment, dict):
            recorded += 1
            verified += int(bool(assessment.get("verified")))
    return {
        "completed_runs_checked": len(rows),
        "evidence_recorded": recorded,
        "verified_runs": verified,
        "coverage": round(verified / len(rows), 4) if rows else 0.0,
    }


def build_operations_status() -> dict[str, Any]:
    from athena_cli import eval_suite, evolution, offline, recovery
    from athena_cli.model_lab import lab_status
    from athena_cli import adaptive_router, distributed_workers, experiments, flows, result_hub, trace_studio, work_packages

    return {
        "evaluations": _safe(eval_suite.status, {"suites": [], "run_count": 0, "latest": None}),
        "memory": _safe(_memory, {"available": False, "active_memories": 0, "safe_archive_candidates": 0}),
        "offline": _safe(lambda: offline.probe_ollama(timeout=0.25), {"ready": False, "models": []}),
        "recovery": _safe(recovery.list_archives, {"archives": [], "latest": None}),
        "evolution": _safe(evolution.status, {"scope": "skills-only", "counts": {}, "total": 0}),
        "model_lab": _safe(lab_status, {"candidates": [], "active": None}),
        "kanban_evidence": _safe(_kanban_evidence, {"completed_runs_checked": 0, "verified_runs": 0, "coverage": 0.0}),
        "traces": _safe(trace_studio.status, {"total": 0, "running": 0}),
        "results": _safe(result_hub.status, {"total": 0, "needs_attention": 0}),
        "flows": _safe(flows.status, {"definitions": [], "counts": {}}),
        "adaptive_router": _safe(adaptive_router.status, {"observations": 0, "enabled_candidates": []}),
        "experiments": _safe(experiments.status, {"total": 0, "counts": {}}),
        "work_packages": _safe(work_packages.list_packages, {"available": [], "installed": []}),
        "distributed_workers": _safe(distributed_workers.status, {"nodes": [], "online": 0, "jobs": {}}),
        "policies_managed_here": False,
    }

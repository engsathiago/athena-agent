"""Local end-to-end traces for model, tool, subagent, and task activity."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from athena_cli.intelligence_db import connection


HANDLED_HOOKS = frozenset({
    "on_session_start", "pre_llm_call", "post_llm_call", "pre_api_request",
    "post_api_request", "api_request_error", "pre_tool_call", "post_tool_call",
    "post_approval_response", "subagent_start", "subagent_stop", "on_session_end",
    "on_session_finalize", "on_session_reset", "context_selected",
})
_SECRET = re.compile(
    r"(?i)(api[_-]?key|authorization|password|passwd|secret|token)(\s*[:=]\s*)([^\s,;\"']+)"
)
_RUNS: dict[tuple[str, str, str], str] = {}
_LOCK = threading.RLock()
_MAX_TEXT = 24_000


def handles_hook(hook_name: str) -> bool:
    return hook_name in HANDLED_HOOKS


def _safe_text(value: Any) -> str:
    text = str(value or "")
    text = _SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", text)
    return text if len(text) <= _MAX_TEXT else text[:_MAX_TEXT] + "…[truncated]"


def _safe_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        return "[depth-limited]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for raw_key, item in list(value.items())[:100]:
            key = str(raw_key)
            if any(marker in key.casefold() for marker in ("authorization", "api_key", "password", "secret", "token")):
                output[key] = "[REDACTED]"
            else:
                output[key] = _safe_value(item, depth=depth + 1)
        return output
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item, depth=depth + 1) for item in list(value)[:100]]
    if hasattr(value, "model_dump"):
        try:
            return _safe_value(value.model_dump(), depth=depth + 1)
        except Exception:
            pass
    return _safe_text(value)


def _json(value: Any) -> str:
    return json.dumps(_safe_value(value), ensure_ascii=False, separators=(",", ":"))


def _key(event: dict[str, Any]) -> tuple[str, str, str]:
    from athena_cli.intelligence_db import database_path

    return (
        str(database_path().resolve()),
        str(event.get("session_id") or ""),
        str(event.get("task_id") or ""),
    )


def _find_run_id(event: dict[str, Any], *, create: bool = True) -> str | None:
    key = _key(event)
    with _LOCK:
        run_id = _RUNS.get(key)
    if run_id:
        return run_id
    _, session_id, task_id = key
    with connection() as conn:
        if session_id and not task_id:
            row = conn.execute(
                """SELECT id FROM trace_runs WHERE session_id=? AND status='running'
                   ORDER BY started_at DESC LIMIT 1""",
                (session_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT id FROM trace_runs
                   WHERE session_id=? AND task_id=? AND status='running'
                   ORDER BY started_at DESC LIMIT 1""",
                (session_id, task_id),
            ).fetchone()
    if row:
        run_id = str(row["id"])
        with _LOCK:
            _RUNS[key] = run_id
        return run_id
    if not create:
        return None
    return start_run(event)


def start_run(event: dict[str, Any]) -> str:
    key = _key(event)
    with _LOCK:
        existing = _RUNS.get(key)
        if existing:
            return existing
        run_id = f"tr_{uuid.uuid4().hex[:20]}"
        _RUNS[key] = run_id
    now = time.time()
    metadata = {
        "cwd": os.getcwd(),
        "evaluation_run_key": os.environ.get("ATHENA_EVAL_RUN_KEY", ""),
        "flow_run_id": os.environ.get("ATHENA_FLOW_RUN_ID", ""),
        "experiment": os.environ.get("ATHENA_EXPERIMENT", ""),
    }
    with connection(write=True) as conn:
        conn.execute(
            """INSERT INTO trace_runs
               (id, run_key, session_id, task_id, parent_session_id, platform,
                model, provider, status, started_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)""",
            (
                run_id, os.environ.get("ATHENA_EVAL_RUN_KEY", ""), key[1], key[2],
                str(event.get("parent_session_id") or ""),
                str(event.get("platform") or ""), str(event.get("model") or ""),
                str(event.get("provider") or ""), now, _json(metadata),
            ),
        )
    return run_id


def _span_key(hook_name: str, event: dict[str, Any]) -> str:
    if hook_name in {"pre_api_request", "post_api_request", "api_request_error"}:
        return str(event.get("api_request_id") or "")
    if "tool_call" in hook_name or hook_name == "post_approval_response":
        return str(event.get("tool_call_id") or "")
    if hook_name.startswith("subagent_"):
        return str(event.get("child_session_id") or event.get("subagent_id") or "")
    return str(event.get("turn_id") or event.get("task_id") or "")


def _event_status(hook_name: str, event: dict[str, Any]) -> str:
    explicit = str(event.get("status") or "")
    if explicit:
        return explicit
    if hook_name == "api_request_error":
        return "error"
    if event.get("failed"):
        return "failed"
    if event.get("interrupted"):
        return "interrupted"
    if event.get("completed"):
        return "completed"
    return ""


def observe_lifecycle(hook_name: str, **event: Any) -> None:
    if hook_name not in HANDLED_HOOKS:
        return
    if hook_name == "on_session_start":
        return
    if hook_name == "pre_llm_call":
        run_id = _find_run_id(event, create=True)
    elif hook_name in {"on_session_finalize", "on_session_reset"}:
        run_id = _find_run_id(event, create=False)
    else:
        run_id = _find_run_id(event, create=True)
    if not run_id:
        return
    now = time.time()
    duration_ms = int(event.get("duration_ms") or 0)
    if not duration_ms and event.get("api_duration") is not None:
        duration_ms = int(float(event.get("api_duration") or 0) * 1000)
    payload = dict(event)
    for key in ("session_id", "task_id", "api_request_id", "tool_call_id"):
        payload.pop(key, None)
    status = _event_status(hook_name, event)
    with connection(write=True) as conn:
        conn.execute(
            """INSERT INTO trace_events
               (run_id, event_type, span_key, parent_span_key, occurred_at,
                duration_ms, status, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, hook_name, _span_key(hook_name, event),
                str(event.get("api_request_id") or event.get("turn_id") or ""),
                now, duration_ms, status, _json(payload),
            ),
        )
        if hook_name == "pre_api_request":
            row = conn.execute("SELECT metadata FROM trace_runs WHERE id=?", (run_id,)).fetchone()
            metadata = json.loads(row["metadata"] or "{}") if row else {}
            if event.get("user_message") and not metadata.get("prompt"):
                metadata["prompt"] = _safe_text(event.get("user_message"))[:4000]
            conn.execute(
                "UPDATE trace_runs SET model_calls=model_calls+1, model=COALESCE(NULLIF(?,''),model), provider=COALESCE(NULLIF(?,''),provider), metadata=? WHERE id=?",
                (str(event.get("model") or ""), str(event.get("provider") or ""), _json(metadata), run_id),
            )
        elif hook_name == "post_api_request":
            usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
            conn.execute(
                """UPDATE trace_runs SET
                   input_tokens=input_tokens+?, output_tokens=output_tokens+?,
                   cache_read_tokens=cache_read_tokens+?, cache_write_tokens=cache_write_tokens+?,
                   estimated_cost_usd=estimated_cost_usd+? WHERE id=?""",
                (
                    int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
                    int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
                    int(usage.get("cache_read_tokens") or 0),
                    int(usage.get("cache_write_tokens") or 0),
                    float(usage.get("estimated_cost_usd") or 0), run_id,
                ),
            )
        elif hook_name == "api_request_error":
            conn.execute("UPDATE trace_runs SET error_count=error_count+1, retries=retries+1 WHERE id=?", (run_id,))
        elif hook_name == "pre_tool_call":
            conn.execute("UPDATE trace_runs SET tool_calls=tool_calls+1 WHERE id=?", (run_id,))
        elif hook_name == "post_llm_call":
            conn.execute(
                "UPDATE trace_runs SET summary=? WHERE id=?",
                (_safe_text(event.get("assistant_response"))[:4000], run_id),
            )
        elif hook_name in {"on_session_end", "on_session_finalize", "on_session_reset"}:
            final_status = "completed" if event.get("completed") else (
                "interrupted" if event.get("interrupted") else "failed" if event.get("failed") else "closed"
            )
            conn.execute(
                "UPDATE trace_runs SET status=?, ended_at=? WHERE id=? AND status='running'",
                (final_status, now, run_id),
            )
    if hook_name in {"on_session_end", "on_session_finalize", "on_session_reset"}:
        with _LOCK:
            _RUNS.pop(_key(event), None)
        try:
            from athena_cli.result_hub import ingest_trace

            ingest_trace(run_id)
        except Exception:
            pass
        try:
            from athena_cli.adaptive_router import record_trace

            record_trace(get_run(run_id))
        except Exception:
            pass


def list_runs(*, limit: int = 50, status: str | None = None, run_key: str | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status=?")
        params.append(status)
    if run_key:
        clauses.append("run_key=?")
        params.append(run_key)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit), 500)))
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM trace_runs {where} ORDER BY started_at DESC LIMIT ?", params
        ).fetchall()
    return [_decode_run(dict(row)) for row in rows]


def get_run(run_id: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute("SELECT * FROM trace_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"trace not found: {run_id}")
        events = conn.execute(
            "SELECT * FROM trace_events WHERE run_id=? ORDER BY occurred_at,id", (run_id,)
        ).fetchall()
    run = _decode_run(dict(row))
    run["events"] = [_decode_event(dict(event)) for event in events]
    run["duration_seconds"] = round(
        max(0.0, float(run.get("ended_at") or time.time()) - float(run["started_at"])), 4
    )
    return run


def find_by_run_key(run_key: str) -> dict[str, Any] | None:
    runs = list_runs(limit=1, run_key=run_key)
    return get_run(runs[0]["id"]) if runs else None


def _decode_run(row: dict[str, Any]) -> dict[str, Any]:
    try:
        row["metadata"] = json.loads(row.get("metadata") or "{}")
    except json.JSONDecodeError:
        row["metadata"] = {}
    return row


def _decode_event(row: dict[str, Any]) -> dict[str, Any]:
    try:
        row["payload"] = json.loads(row.get("payload") or "{}")
    except json.JSONDecodeError:
        row["payload"] = {}
    return row


def replay_manifest(run_id: str) -> dict[str, Any]:
    run = get_run(run_id)
    prompts = []
    for event in run["events"]:
        if event["event_type"] == "pre_api_request":
            prompt = event["payload"].get("user_message")
            if prompt:
                prompts.append(prompt)
    return {
        "source_trace": run_id,
        "model": run.get("model"),
        "provider": run.get("provider"),
        "platform": run.get("platform"),
        "prompt": prompts[0] if prompts else "",
        "event_digest": hashlib.sha256(_json(run["events"]).encode()).hexdigest(),
        "replay_command": f"athena -m {run.get('model') or '<model>'} -z <prompt>",
    }


def prune(*, max_age_days: int = 30, keep_latest: int = 5000, execute: bool = False) -> dict[str, Any]:
    """Preview or remove old completed traces while preserving recent history."""
    days = max(1, int(max_age_days))
    keep = max(100, int(keep_latest))
    cutoff = time.time() - days * 86400
    with connection(write=execute) as conn:
        rows = conn.execute(
            """SELECT id FROM trace_runs
               WHERE status != 'running' AND (
                 COALESCE(ended_at, started_at) < ? OR id NOT IN (
                   SELECT id FROM trace_runs ORDER BY started_at DESC LIMIT ?
                 )
               )""",
            (cutoff, keep),
        ).fetchall()
        ids = [str(row["id"]) for row in rows]
        if execute and ids:
            conn.executemany("DELETE FROM trace_runs WHERE id=?", ((run_id,) for run_id in ids))
    if execute and ids:
        with _LOCK:
            removed = set(ids)
            for key, run_id in list(_RUNS.items()):
                if run_id in removed:
                    _RUNS.pop(key, None)
    return {
        "executed": execute,
        "removed" if execute else "would_remove": len(ids),
        "max_age_days": days,
        "keep_latest": keep,
    }


def status() -> dict[str, Any]:
    with connection() as conn:
        totals = conn.execute(
            """SELECT COUNT(*) total,
               SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) running,
               SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) completed,
               SUM(error_count) errors, SUM(model_calls) model_calls,
               SUM(tool_calls) tool_calls FROM trace_runs"""
        ).fetchone()
    latest = list_runs(limit=1)
    values = {key: int(totals[key] or 0) for key in totals.keys()}
    return {**values, "latest": latest[0] if latest else None}

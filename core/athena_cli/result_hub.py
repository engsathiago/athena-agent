"""Unified review inbox and versioned artifact catalog."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from athena_constants import get_athena_home
from athena_cli.intelligence_db import connection


VALID_STATUSES = {"ready", "waiting", "approved", "changes_requested", "archived", "failed"}


def _now() -> float:
    return time.time()


def _artifact_root(item_id: str) -> Path:
    return get_athena_home() / "results" / "artifacts" / item_id


def create_item(
    *, source_type: str, source_id: str, title: str, summary: str = "",
    status: str = "ready", metadata: dict[str, Any] | None = None,
    artifacts: Iterable[str | Path] = (),
) -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid result status: {status}")
    now = _now()
    item_id = f"result_{uuid.uuid4().hex[:20]}"
    with connection(write=True) as conn:
        existing = conn.execute(
            "SELECT id FROM review_items WHERE source_type=? AND source_id=?",
            (source_type, source_id),
        ).fetchone()
        if existing:
            item_id = str(existing["id"])
            conn.execute(
                "UPDATE review_items SET title=?,summary=?,status=?,updated_at=?,metadata=? WHERE id=?",
                (title, summary, status, now, json.dumps(metadata or {}, ensure_ascii=False), item_id),
            )
        else:
            conn.execute(
                """INSERT INTO review_items
                   (id,source_type,source_id,title,summary,status,created_at,updated_at,metadata)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (item_id, source_type, source_id, title, summary, status, now, now,
                 json.dumps(metadata or {}, ensure_ascii=False)),
            )
    for artifact in artifacts:
        add_artifact(item_id, artifact)
    return get_item(item_id)


def add_artifact(item_id: str, source: str | Path, *, name: str | None = None) -> dict[str, Any]:
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"artifact not found: {path}")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    display_name = Path(str(name or path.name)).name.strip()
    if display_name in {"", ".", ".."}:
        raise ValueError("invalid artifact name")
    with connection() as conn:
        exists = conn.execute("SELECT id FROM review_items WHERE id=?", (item_id,)).fetchone()
        if exists is None:
            raise FileNotFoundError(f"result not found: {item_id}")
        row = conn.execute(
            "SELECT COALESCE(MAX(version),0) version FROM review_artifacts WHERE item_id=? AND name=?",
            (item_id, display_name),
        ).fetchone()
        version = int(row["version"]) + 1
    target_dir = _artifact_root(item_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"v{version}-{display_name}"
    shutil.copy2(path, target)
    artifact_id = f"artifact_{uuid.uuid4().hex[:20]}"
    media_type = mimetypes.guess_type(display_name)[0] or "application/octet-stream"
    with connection(write=True) as conn:
        conn.execute(
            """INSERT INTO review_artifacts
               (id,item_id,name,path,media_type,size_bytes,sha256,version,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (artifact_id, item_id, display_name, str(target), media_type, len(data), digest, version, _now()),
        )
        conn.execute("UPDATE review_items SET updated_at=? WHERE id=?", (_now(), item_id))
    return {
        "id": artifact_id, "item_id": item_id, "name": display_name,
        "path": str(target), "media_type": media_type, "size_bytes": len(data),
        "sha256": digest, "version": version,
    }


def update_status(item_id: str, status: str, *, note: str = "") -> dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid result status: {status}")
    with connection(write=True) as conn:
        row = conn.execute("SELECT metadata FROM review_items WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"result not found: {item_id}")
        metadata = json.loads(row["metadata"] or "{}")
        history = metadata.setdefault("review_history", [])
        history.append({"status": status, "note": note, "at": _now()})
        conn.execute(
            "UPDATE review_items SET status=?,updated_at=?,metadata=? WHERE id=?",
            (status, _now(), json.dumps(metadata, ensure_ascii=False), item_id),
        )
    return get_item(item_id)


def list_items(*, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ""
    if status:
        where = "WHERE status=?"
        params.append(status)
    params.append(max(1, min(int(limit), 500)))
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM review_items {where} ORDER BY updated_at DESC LIMIT ?", params
        ).fetchall()
    return [_decode_item(dict(row)) for row in rows]


def get_item(item_id: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute("SELECT * FROM review_items WHERE id=?", (item_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"result not found: {item_id}")
        artifacts = conn.execute(
            "SELECT * FROM review_artifacts WHERE item_id=? ORDER BY name,version DESC", (item_id,)
        ).fetchall()
    result = _decode_item(dict(row))
    result["artifacts"] = [dict(item) for item in artifacts]
    return result


def _decode_item(row: dict[str, Any]) -> dict[str, Any]:
    try:
        row["metadata"] = json.loads(row.get("metadata") or "{}")
    except json.JSONDecodeError:
        row["metadata"] = {}
    return row


def ingest_trace(trace_id: str) -> dict[str, Any] | None:
    from athena_cli.trace_studio import get_run

    trace = get_run(trace_id)
    if trace.get("status") == "running":
        return None
    title = trace.get("summary") or f"Execução {trace_id}"
    title = " ".join(str(title).split())[:140]
    review_status = "ready" if trace.get("status") in {"completed", "closed"} else "failed"
    return create_item(
        source_type="trace", source_id=trace_id, title=title,
        summary=str(trace.get("summary") or "")[:4000], status=review_status,
        metadata={
            "trace_id": trace_id, "session_id": trace.get("session_id"),
            "model": trace.get("model"), "provider": trace.get("provider"),
            "tokens": int(trace.get("input_tokens") or 0) + int(trace.get("output_tokens") or 0),
            "cost_usd": trace.get("estimated_cost_usd"),
        },
    )


def status() -> dict[str, Any]:
    with connection() as conn:
        rows = conn.execute("SELECT status,COUNT(*) count FROM review_items GROUP BY status").fetchall()
        artifact = conn.execute(
            "SELECT COUNT(*) count,COALESCE(SUM(size_bytes),0) bytes FROM review_artifacts"
        ).fetchone()
    counts = {str(row["status"]): int(row["count"]) for row in rows}
    return {
        "counts": counts, "total": sum(counts.values()),
        "needs_attention": counts.get("ready", 0) + counts.get("waiting", 0) + counts.get("failed", 0),
        "artifacts": int(artifact["count"]), "artifact_bytes": int(artifact["bytes"]),
        "latest": list_items(limit=5),
    }

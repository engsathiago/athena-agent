"""Deterministic canary experiments with automatic promotion or rollback."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from athena_cli.intelligence_db import connection


def create(
    name: str, *, kind: str, baseline: str, candidate: str,
    traffic_percent: float = 5.0, min_samples: int = 20,
    max_regression: float = 0.02, metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    traffic = max(0.1, min(float(traffic_percent), 50.0))
    now = time.time()
    experiment_id = f"exp_{uuid.uuid4().hex[:20]}"
    with connection(write=True) as conn:
        conn.execute(
            """INSERT INTO experiments
               (id,name,kind,baseline,candidate,traffic_percent,status,min_samples,max_regression,created_at,updated_at,metadata)
               VALUES (?,?,?,?,?,?,'draft',?,?,?,?,?)""",
            (experiment_id, name, kind, baseline, candidate, traffic, max(2, int(min_samples)),
             abs(float(max_regression)), now, now, json.dumps(metadata or {}, ensure_ascii=False)),
        )
    return get(experiment_id)


def get(value: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute("SELECT * FROM experiments WHERE id=? OR name=?", (value, value)).fetchone()
    if row is None:
        raise FileNotFoundError(f"experiment not found: {value}")
    result = dict(row)
    result["metadata"] = json.loads(result.get("metadata") or "{}")
    return result


def set_status(value: str, status: str) -> dict[str, Any]:
    if status not in {"draft", "running", "promoted", "rolled_back", "paused"}:
        raise ValueError(f"invalid experiment status: {status}")
    experiment = get(value)
    with connection(write=True) as conn:
        conn.execute("UPDATE experiments SET status=?,updated_at=? WHERE id=?", (status, time.time(), experiment["id"]))
    return get(experiment["id"])


def assign(value: str, subject_key: str) -> dict[str, Any]:
    experiment = get(value)
    if experiment["status"] != "running":
        variant = "baseline"
    else:
        digest = hashlib.sha256(f"{experiment['id']}:{subject_key}".encode()).digest()
        bucket = int.from_bytes(digest[:8], "big") / (2**64 - 1) * 100
        variant = "candidate" if bucket < float(experiment["traffic_percent"]) else "baseline"
    return {"experiment": experiment["id"], "variant": variant, "value": experiment[variant]}


def record(value: str, variant: str, score: float) -> dict[str, Any]:
    if variant not in {"baseline", "candidate"}:
        raise ValueError("variant must be baseline or candidate")
    experiment = get(value)
    count_field = f"{variant}_runs"
    score_field = f"{variant}_score"
    count = int(experiment[count_field])
    average = float(experiment[score_field])
    new_average = ((average * count) + float(score)) / (count + 1)
    with connection(write=True) as conn:
        conn.execute(
            f"UPDATE experiments SET {count_field}=?,{score_field}=?,updated_at=? WHERE id=?",
            (count + 1, new_average, time.time(), experiment["id"]),
        )
    return evaluate(experiment["id"])


def evaluate(value: str) -> dict[str, Any]:
    experiment = get(value)
    minimum = int(experiment["min_samples"])
    if min(int(experiment["baseline_runs"]), int(experiment["candidate_runs"])) < minimum:
        decision = "collecting"
    else:
        delta = float(experiment["candidate_score"]) - float(experiment["baseline_score"])
        decision = "rollback" if delta < -float(experiment["max_regression"]) else "promote" if delta > 0 else "keep"
        if decision == "rollback" and experiment["status"] == "running":
            set_status(experiment["id"], "rolled_back")
        elif decision == "promote" and experiment["status"] == "running":
            set_status(experiment["id"], "promoted")
    latest = get(experiment["id"])
    latest["decision"] = decision
    latest["delta"] = float(latest["candidate_score"]) - float(latest["baseline_score"])
    return latest


def status() -> dict[str, Any]:
    with connection() as conn:
        rows = conn.execute("SELECT id FROM experiments ORDER BY updated_at DESC").fetchall()
    items = [evaluate(str(row["id"])) for row in rows]
    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {"experiments": items, "counts": counts, "total": len(items)}

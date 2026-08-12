"""Small, deterministic helpers for evidence-based task handoffs.

The helpers deliberately do not run tools or call a model.  They turn evidence
already produced by a worker into a compact, auditable completion assessment.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping


_PASSING_STATUSES = {
    "complete",
    "completed",
    "executed",
    "passed",
    "success",
    "succeeded",
    "verified",
}
_FAILING_STATUSES = {"error", "failed", "failure"}
_MAX_EVIDENCE_ITEMS = 20
_MAX_FIELD_CHARS = 2000


def normalize_completion_evidence(value: Any) -> list[dict[str, Any]]:
    """Return a bounded list of JSON-safe evidence records."""

    if value is None:
        return []
    raw_items: Iterable[Any]
    if isinstance(value, (str, Mapping)):
        raw_items = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = value
    else:
        raise ValueError("evidence must be a string, object, or list")

    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if len(normalized) >= _MAX_EVIDENCE_ITEMS:
            break
        if isinstance(item, str):
            summary = " ".join(item.split())[:_MAX_FIELD_CHARS]
            if summary:
                normalized.append({"kind": "note", "summary": summary, "status": "claimed"})
            continue
        if not isinstance(item, Mapping):
            raise ValueError("each evidence item must be a string or object")

        record: dict[str, Any] = {}
        for key in ("kind", "summary", "command", "path", "status", "scope"):
            raw = item.get(key)
            if raw is not None and str(raw).strip():
                record[key] = " ".join(str(raw).split())[:_MAX_FIELD_CHARS]
        if "exit_code" in item and item.get("exit_code") is not None:
            record["exit_code"] = int(item["exit_code"])
        if not record:
            continue
        record.setdefault("kind", "note")
        if "status" not in record:
            record["status"] = (
                "passed" if record.get("exit_code") == 0 else "claimed"
            )
        normalized.append(record)
    return normalized


def artifact_evidence(paths: Iterable[str] | None) -> list[dict[str, Any]]:
    """Describe declared deliverables without reading their contents."""

    records: list[dict[str, Any]] = []
    for raw in list(paths or [])[:_MAX_EVIDENCE_ITEMS]:
        path = Path(str(raw)).expanduser()
        exists = path.exists()
        records.append(
            {
                "kind": "artifact",
                "path": str(path),
                "status": "verified" if exists else "failed",
                "summary": "deliverable exists" if exists else "deliverable is missing",
            }
        )
    return records


def assess_completion_evidence(evidence: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Classify a handoff as verified, failed, or an unsupported claim."""

    items = [dict(item) for item in evidence]
    passed = 0
    failed = 0
    for item in items:
        status = str(item.get("status") or "").strip().lower()
        exit_code = item.get("exit_code")
        if status in _PASSING_STATUSES or exit_code == 0:
            passed += 1
        elif status in _FAILING_STATUSES or (
            isinstance(exit_code, int) and exit_code != 0
        ):
            failed += 1

    if failed:
        status = "failed"
    elif passed:
        status = "verified"
    else:
        status = "claimed"
    return {
        "status": status,
        "verified": status == "verified",
        "passed_count": passed,
        "failed_count": failed,
        "evidence_count": len(items),
    }

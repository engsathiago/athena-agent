"""Local, dependency-free model dataset/evaluation/activation laboratory."""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping

from athena_constants import get_athena_home


_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[opsu]_[A-Za-z0-9]{20,}\b"),
)
_PII_PATTERNS = (
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"),
    re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-\s]?\d{4}(?!\d)"),
)


def lab_root() -> Path:
    return get_athena_home() / "model-lab"


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _redact_text(text: str) -> tuple[str, int]:
    count = 0
    clean = text
    for pattern in (*_SECRET_PATTERNS, *_PII_PATTERNS):
        clean, replacements = pattern.subn("[REDACTED]", clean)
        count += replacements
    return clean, count


def _redact_value(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        output = []
        total = 0
        for item in value:
            cleaned, count = _redact_value(item)
            output.append(cleaned)
            total += count
        return output, total
    if isinstance(value, dict):
        output = {}
        total = 0
        for key, item in value.items():
            cleaned, count = _redact_value(item)
            output[str(key)] = cleaned
            total += count
        return output, total
    return value, 0


def _valid_training_record(record: Mapping[str, Any]) -> bool:
    messages = record.get("messages")
    if isinstance(messages, list) and len(messages) >= 2:
        return all(
            isinstance(item, dict)
            and str(item.get("role") or "").strip()
            and str(item.get("content") or "").strip()
            for item in messages
        )
    pairs = (("input", "output"), ("prompt", "response"), ("instruction", "response"))
    return any(
        str(record.get(left) or "").strip() and str(record.get(right) or "").strip()
        for left, right in pairs
    )


def prepare_dataset(input_path: str | Path, *, name: str = "dataset") -> dict[str, Any]:
    """Redact, validate, deduplicate, and freeze a source JSONL dataset."""

    source = Path(input_path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"input JSONL does not exist: {source}")

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    redactions = 0
    for line_number, raw_line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        raw_hash = hashlib.sha256(raw_line.encode("utf-8")).hexdigest()
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            rejected.append({"line": line_number, "reason": "invalid_json", "sha256": raw_hash})
            continue
        if not isinstance(record, dict) or not _valid_training_record(record):
            rejected.append({"line": line_number, "reason": "invalid_schema", "sha256": raw_hash})
            continue
        cleaned, count = _redact_value(record)
        canonical = json.dumps(cleaned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if digest in seen:
            rejected.append({"line": line_number, "reason": "duplicate", "sha256": raw_hash})
            continue
        seen.add(digest)
        redactions += count
        accepted.append(cleaned)

    payload = "".join(
        json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in accepted
    )
    dataset_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-") or "dataset"
    target_dir = lab_root() / "datasets" / f"{safe_name}-{dataset_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = target_dir / "dataset.jsonl"
    if dataset_path.exists() and dataset_path.read_text(encoding="utf-8") != payload:
        raise RuntimeError(f"immutable dataset collision at {dataset_path}")
    dataset_path.write_text(payload, encoding="utf-8")
    manifest = {
        "dataset_id": dataset_id,
        "name": safe_name,
        "source": str(source),
        "records": len(accepted),
        "rejected": len(rejected),
        "redactions": redactions,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "dataset_path": str(dataset_path),
        "created_at": int(time.time()),
    }
    _atomic_json(target_dir / "manifest.json", manifest)
    _atomic_json(target_dir / "rejected.json", rejected)
    return manifest


def _metrics_from_file(path: str | Path) -> dict[str, float]:
    raw = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    values = raw.get("metrics", raw) if isinstance(raw, dict) else None
    if not isinstance(values, dict) or not values:
        raise ValueError(f"metrics file must contain a non-empty object: {path}")
    metrics: dict[str, float] = {}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        metrics[str(key)] = float(value)
    if not metrics:
        raise ValueError(f"metrics file has no numeric metrics: {path}")
    return metrics


def compare_models(
    baseline_path: str | Path,
    candidate_path: str | Path,
    *,
    candidate_name: str,
    max_regression: float = 0.02,
    min_improvement: float = 0.0,
    required: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Compare metric JSON files and persist an auditable gate decision."""

    baseline = _metrics_from_file(baseline_path)
    candidate = _metrics_from_file(candidate_path)
    shared = sorted(set(baseline) & set(candidate))
    if not shared:
        raise ValueError("baseline and candidate have no metrics in common")
    deltas = {name: candidate[name] - baseline[name] for name in shared}
    mean_delta = sum(deltas.values()) / len(deltas)
    regressions = {
        name: delta for name, delta in deltas.items() if delta < -abs(max_regression)
    }
    gate_failures = {
        name: {"actual": candidate.get(name), "minimum": minimum}
        for name, minimum in (required or {}).items()
        if candidate.get(name, float("-inf")) < float(minimum)
    }
    decision = (
        "accept"
        if not regressions and not gate_failures and mean_delta >= min_improvement
        else "reject"
    )
    report = {
        "candidate": candidate_name,
        "decision": decision,
        "baseline": baseline,
        "candidate_metrics": candidate,
        "deltas": deltas,
        "mean_delta": mean_delta,
        "max_regression": max_regression,
        "min_improvement": min_improvement,
        "regressions": regressions,
        "gate_failures": gate_failures,
        "created_at": int(time.time()),
    }
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", candidate_name).strip("-") or "candidate"
    report_path = lab_root() / "evaluations" / f"{safe_name}-{int(time.time())}.json"
    report["report_path"] = str(report_path)
    _atomic_json(report_path, report)
    return report


def _registry_path() -> Path:
    return lab_root() / "registry.json"


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {"candidates": {}, "active": None, "history": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("candidates", {})
    data.setdefault("active", None)
    data.setdefault("history", [])
    return data


def register_candidate(name: str, model_ref: str, *, evaluation: str | None = None) -> dict[str, Any]:
    registry = _load_registry()
    report = None
    if evaluation:
        report = json.loads(Path(evaluation).expanduser().read_text(encoding="utf-8"))
    entry = {
        "name": name,
        "model_ref": model_ref,
        "evaluation": str(Path(evaluation).expanduser().resolve()) if evaluation else None,
        "decision": report.get("decision") if isinstance(report, dict) else "unverified",
        "registered_at": int(time.time()),
    }
    registry["candidates"][name] = entry
    _atomic_json(_registry_path(), registry)
    return entry


def activate_candidate(name: str, *, allow_unverified: bool = False) -> dict[str, Any]:
    registry = _load_registry()
    candidate = registry["candidates"].get(name)
    if not candidate:
        raise ValueError(f"unknown candidate: {name}")
    if candidate.get("decision") != "accept" and not allow_unverified:
        raise ValueError("candidate has not passed evaluation; use an accepted report first")
    previous = registry.get("active")
    registry["active"] = name
    registry["history"].append(
        {"from": previous, "to": name, "activated_at": int(time.time())}
    )
    _atomic_json(_registry_path(), registry)
    return {"active": name, "previous": previous, "model_ref": candidate["model_ref"]}


def rollback_candidate() -> dict[str, Any]:
    registry = _load_registry()
    history = registry.get("history") or []
    if not history:
        raise ValueError("no activation history to roll back")
    last = history.pop()
    current = registry.get("active")
    registry["active"] = last.get("from")
    registry["history"] = history
    _atomic_json(_registry_path(), registry)
    return {"active": registry["active"], "rolled_back_from": current}


def lab_status() -> dict[str, Any]:
    return _load_registry()

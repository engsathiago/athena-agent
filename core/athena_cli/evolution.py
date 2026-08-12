"""Controlled, reversible evolution for Athena skills.

This workflow deliberately operates only on ``ATHENA_HOME/skills``.  Core
code, identity files and policy prompts are outside its writable scope.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from athena_constants import get_athena_home


def _root() -> Path:
    return get_athena_home() / "evolution" / "proposals"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value)).strip("-.")
    if not name or name in {".", ".."}:
        raise ValueError("invalid skill name")
    return name


def _proposal_path(proposal_id: str) -> Path:
    path = (_root() / _safe_name(proposal_id)).resolve()
    path.relative_to(_root().resolve())
    if not path.is_dir():
        raise FileNotFoundError(f"proposal not found: {proposal_id}")
    return path


def _read(path: Path) -> dict[str, Any]:
    return json.loads((path / "proposal.json").read_text(encoding="utf-8"))


def _write(path: Path, data: dict[str, Any]) -> None:
    target = path / "proposal.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, target)


def _manifest(source: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        values[str(path.relative_to(source))] = digest
    return values


def propose(source: str | Path, *, name: str | None = None, reason: str = "") -> dict[str, Any]:
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_dir() or not (source_path / "SKILL.md").is_file():
        raise ValueError("a proposal must be a skill directory containing SKILL.md")
    if any(path.is_symlink() for path in source_path.rglob("*")):
        raise ValueError("skill proposals cannot contain symbolic links")
    skill_name = _safe_name(name or source_path.name)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    proposal_id = f"{stamp}-{skill_name}"
    path = _root() / proposal_id
    path.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source_path, path / "candidate", symlinks=False)
    data = {
        "schema_version": 1,
        "id": proposal_id,
        "kind": "skill",
        "skill": skill_name,
        "reason": str(reason).strip(),
        "status": "proposed",
        "created_at": _now(),
        "candidate_manifest": _manifest(path / "candidate"),
        "evaluation": None,
        "activated_at": None,
        "rolled_back_at": None,
    }
    _write(path, data)
    return data


def evaluate(proposal_id: str, report: str | Path, *, min_score: float = 0.8) -> dict[str, Any]:
    path = _proposal_path(proposal_id)
    data = _read(path)
    report_path = Path(report).expanduser().resolve()
    result = json.loads(report_path.read_text(encoding="utf-8"))
    if "accepted" in result:
        accepted = bool(result["accepted"])
    elif "decision" in result:
        accepted = str(result["decision"]).lower() == "accept"
    else:
        accepted = float(result.get("score", 0.0)) >= float(min_score) and int(result.get("failed", 0)) == 0
    data["status"] = "accepted" if accepted else "rejected"
    data["evaluation"] = {
        "report": str(report_path),
        "score": result.get("score", result.get("candidate_score")),
        "decision": "accept" if accepted else "reject",
        "evaluated_at": _now(),
        "min_score": float(min_score),
    }
    _write(path, data)
    return data


def activate(proposal_id: str) -> dict[str, Any]:
    path = _proposal_path(proposal_id)
    data = _read(path)
    if data.get("status") != "accepted":
        raise ValueError("proposal must pass evaluation before activation")
    candidate = path / "candidate"
    if _manifest(candidate) != data.get("candidate_manifest"):
        raise ValueError("candidate changed after proposal; create a new proposal")
    skills_root = get_athena_home() / "skills"
    skills_root.mkdir(parents=True, exist_ok=True)
    target = skills_root / _safe_name(data["skill"])
    staging = skills_root / f".{target.name}.activate-{proposal_id}"
    displaced = path / "displaced-live"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(candidate, staging)
    had_previous = target.exists()
    try:
        if had_previous:
            if displaced.exists():
                shutil.rmtree(displaced)
            os.replace(target, displaced)
        os.replace(staging, target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        if had_previous and displaced.exists() and not target.exists():
            os.replace(displaced, target)
        raise
    data["status"] = "active"
    data["activated_at"] = _now()
    data["target"] = str(target)
    data["had_previous"] = had_previous
    _write(path, data)
    return data


def rollback(proposal_id: str) -> dict[str, Any]:
    path = _proposal_path(proposal_id)
    data = _read(path)
    if data.get("status") != "active":
        raise ValueError("only an active proposal can be rolled back")
    target = get_athena_home() / "skills" / _safe_name(data["skill"])
    displaced = path / "displaced-live"
    removed = path / "rolled-back-candidate"
    if target.exists():
        if removed.exists():
            shutil.rmtree(removed)
        os.replace(target, removed)
    if data.get("had_previous"):
        if not displaced.exists():
            raise FileNotFoundError("previous skill snapshot is missing")
        os.replace(displaced, target)
    data["status"] = "rolled_back"
    data["rolled_back_at"] = _now()
    _write(path, data)
    return data


def inspect_signals(*, limit: int = 20) -> dict[str, Any]:
    """Collect recent quality/task failures without changing any files."""

    limit = max(1, min(int(limit), 100))
    evaluation_failures: list[dict[str, Any]] = []
    try:
        from athena_cli.eval_suite import status as eval_status

        latest = eval_status().get("latest") or {}
        report_path = latest.get("report_path")
        if report_path:
            report = json.loads(Path(report_path).read_text(encoding="utf-8"))
            evaluation_failures = [
                {
                    "id": result.get("id"),
                    "error": result.get("error"),
                    "tags": result.get("tags") or [],
                    "failed_checks": [
                        check.get("check")
                        for check in result.get("checks") or []
                        if not check.get("passed")
                    ],
                }
                for result in report.get("results") or []
                if not result.get("passed")
            ][:limit]
    except (OSError, ValueError, json.JSONDecodeError):
        evaluation_failures = []

    task_failures: list[dict[str, Any]] = []
    try:
        from athena_cli.kanban_db import kanban_db_path

        db_path = kanban_db_path()
        if db_path.is_file():
            connection = sqlite3.connect(
                f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True
            )
            connection.row_factory = sqlite3.Row
            try:
                rows = connection.execute(
                    """
                    SELECT r.task_id, t.title, r.outcome, r.error, r.summary, r.ended_at
                    FROM task_runs r JOIN tasks t ON t.id = r.task_id
                    WHERE r.outcome IN ('blocked', 'crashed', 'timed_out', 'failed', 'gave_up')
                    ORDER BY r.ended_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            finally:
                connection.close()
            task_failures = [dict(row) for row in rows]
    except (OSError, sqlite3.DatabaseError):
        task_failures = []

    labels = []
    for item in task_failures:
        raw = str(item.get("error") or item.get("summary") or item.get("outcome") or "")
        label = " ".join(raw.split()).casefold()[:160]
        if label:
            labels.append(label)
    repeated = [
        {"signal": label, "occurrences": count}
        for label, count in Counter(labels).most_common(10)
        if count > 1
    ]
    return {
        "evaluation_failures": evaluation_failures,
        "task_failures": task_failures,
        "repeated_failures": repeated,
        "total": len(evaluation_failures) + len(task_failures),
        "next": "Review a repeated signal, build a candidate skill, then use evolve propose and attach an evals report before activation.",
    }


def status() -> dict[str, Any]:
    proposals = []
    if _root().exists():
        for path in sorted(_root().iterdir(), reverse=True):
            try:
                proposals.append(_read(path))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
    counts: dict[str, int] = {}
    for proposal in proposals:
        key = str(proposal.get("status") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return {"scope": "skills-only", "proposals": proposals[:50], "counts": counts, "total": len(proposals), "signals": inspect_signals()}

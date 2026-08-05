"""Quiet, profile-scoped proactive heartbeat built on Athena cron."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


HEARTBEAT_JOB_PREFIX = "athena-heartbeat:"


def _home() -> Path:
    value = os.environ.get("ATHENA_HOME", "").strip()
    return Path(value).expanduser().resolve() if value else (Path.home() / ".athena").resolve()


def _state_path() -> Path:
    return _home() / "heartbeats.yaml"


def _read_state() -> dict[str, Any]:
    try:
        import yaml

        data = yaml.safe_load(_state_path().read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("version", 1)
    if not isinstance(data.get("agents"), dict):
        data["agents"] = {}
    return data


def _write_state(data: dict[str, Any]) -> None:
    import yaml

    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".yaml.tmp")
    temp.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(temp, path)


def _prompt(agent: str, active_hours: str) -> str:
    return f"""Athena quiet heartbeat for agent {agent}.

Read HEARTBEAT.md in this agent's profile and inspect only the durable state
needed for its checklist. Active hours are {active_hours}; outside that window,
respond exactly [SILENT]. If there is no new, relevant and actionable change,
respond exactly [SILENT]. Otherwise send one concise update containing only the
change, why it matters, and the recommended next action. Never manufacture work
just to produce a heartbeat response.
"""


def enable_heartbeat(
    agent: str,
    *,
    schedule: str = "every 30m",
    deliver: str = "local",
    active_hours: str = "08:00-22:00",
) -> dict[str, Any]:
    from athena.agents import agent_path, get_agent
    from cron.jobs import create_job, list_jobs, resume_job, update_job, use_cron_store

    agent_id = str(agent).strip().lower()
    if get_agent(agent_id) is None:
        raise ValueError(f"Athena agent {agent_id!r} does not exist")
    profile_home = agent_path(agent_id)
    heartbeat_file = profile_home / "HEARTBEAT.md"
    if not heartbeat_file.exists():
        template = Path(__file__).resolve().parent / "templates" / "HEARTBEAT.md"
        heartbeat_file.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")

    job_name = HEARTBEAT_JOB_PREFIX + agent_id
    with use_cron_store(profile_home):
        existing = next((job for job in list_jobs(include_disabled=True) if job.get("name") == job_name), None)
        if existing:
            update_job(
                existing["id"],
                {
                    "prompt": _prompt(agent_id, active_hours),
                    "schedule": schedule,
                    "deliver": deliver,
                    "workdir": str(profile_home / "workspace"),
                },
            )
            job = resume_job(existing["id"]) or existing
        else:
            job = create_job(
                prompt=_prompt(agent_id, active_hours),
                schedule=schedule,
                name=job_name,
                deliver=deliver,
                workdir=str(profile_home / "workspace"),
            )

    state = _read_state()
    record = {
        "enabled": True,
        "job_id": job["id"],
        "schedule": schedule,
        "deliver": deliver,
        "active_hours": active_hours,
        "profile_home": str(profile_home),
    }
    state["agents"][agent_id] = record
    _write_state(state)
    return record


def disable_heartbeat(agent: str) -> bool:
    from athena.agents import agent_path
    from cron.jobs import pause_job, use_cron_store

    agent_id = str(agent).strip().lower()
    state = _read_state()
    record = state["agents"].get(agent_id)
    if not isinstance(record, dict):
        return False
    with use_cron_store(agent_path(agent_id)):
        pause_job(str(record.get("job_id", "")))
    record["enabled"] = False
    _write_state(state)
    return True


def heartbeat_status(agent: str | None = None) -> dict[str, Any]:
    agents = _read_state()["agents"]
    if agent is None:
        return dict(agents)
    value = agents.get(str(agent).strip().lower())
    return dict(value) if isinstance(value, dict) else {}

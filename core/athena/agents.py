"""First-class Athena agents backed by isolated Athena profiles."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class AgentSpec:
    id: str
    path: str
    description: str = ""
    created_at: float = 0.0
    source: str = "athena"
    is_default: bool = False


def athena_home() -> Path:
    value = os.environ.get("ATHENA_HOME", "").strip()
    return Path(value).expanduser().resolve() if value else (Path.home() / ".athena").resolve()


def agent_path(agent_id: str) -> Path:
    if agent_id == "default":
        return athena_home()
    return athena_home() / "profiles" / agent_id


def _manifest_path(path: Path) -> Path:
    return path / "athena-agent.json"


def _read_manifest(path: Path, agent_id: str) -> AgentSpec:
    data: dict[str, Any] = {}
    try:
        loaded = json.loads(_manifest_path(path).read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    except Exception:
        pass
    description = str(data.get("description") or "")
    if not description:
        try:
            import yaml

            meta = yaml.safe_load((path / "profile.yaml").read_text(encoding="utf-8")) or {}
            if isinstance(meta, dict):
                description = str(meta.get("description") or "")
        except Exception:
            pass
    try:
        created = float(data.get("created_at") or path.stat().st_ctime)
    except Exception:
        created = 0.0
    return AgentSpec(
        id=agent_id,
        path=str(path),
        description=description,
        created_at=created,
        source=str(data.get("source") or ("athena" if data else "athena-profile")),
        is_default=agent_id == "default",
    )


def ensure_default_manifest() -> Path:
    home = athena_home()
    path = _manifest_path(home)
    if path.exists():
        return path
    payload = AgentSpec(
        id="default",
        path=str(home),
        description="Athena primary personal agent",
        created_at=time.time(),
        source="athena",
        is_default=True,
    )
    path.write_text(json.dumps(asdict(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def list_agents() -> list[AgentSpec]:
    ensure_default_manifest()
    result = [_read_manifest(athena_home(), "default")]
    profiles = athena_home() / "profiles"
    if profiles.is_dir():
        for entry in sorted(profiles.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                result.append(_read_manifest(entry, entry.name))
    return result


def get_agent(agent_id: str) -> Optional[AgentSpec]:
    canonical = str(agent_id).strip().lower()
    for agent in list_agents():
        if agent.id == canonical:
            return agent
    return None


def _personalized_soul(agent_id: str, description: str) -> str:
    template = (Path(__file__).resolve().parent / "templates" / "SOUL.md").read_text(encoding="utf-8")
    identity = ["", "## Agent instance", "", f"- Agent ID: `{agent_id}`"]
    if description:
        identity.append(f"- Purpose: {description}")
    identity.append("- This agent owns an isolated workspace, sessions, skills, credentials, cron and memory store.")
    return template.rstrip() + "\n" + "\n".join(identity) + "\n"


def create_agent(agent_id: str, *, description: str = "", clone_from: str = "default") -> AgentSpec:
    """Create an isolated Athena agent using Athena' proven profile boundary."""

    from athena_cli.profiles import create_profile, normalize_profile_name

    canonical = normalize_profile_name(agent_id)
    path = create_profile(
        canonical,
        clone_from=clone_from,
        clone_config=True,
        no_alias=True,
        description=description or None,
    )
    (path / "SOUL.md").write_text(
        _personalized_soul(canonical, description), encoding="utf-8"
    )
    heartbeat_template = Path(__file__).resolve().parent / "templates" / "HEARTBEAT.md"
    (path / "HEARTBEAT.md").write_text(
        heartbeat_template.read_text(encoding="utf-8"), encoding="utf-8"
    )
    payload = AgentSpec(
        id=canonical,
        path=str(path),
        description=description,
        created_at=time.time(),
        source=f"clone:{clone_from}",
        is_default=False,
    )
    _manifest_path(path).write_text(
        json.dumps(asdict(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def use_agent(agent_id: str) -> None:
    from athena_cli.profiles import set_active_profile

    set_active_profile(str(agent_id).strip().lower())

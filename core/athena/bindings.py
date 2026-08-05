"""Deterministic channel/peer-to-agent bindings inspired by OpenClaw."""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional


def _home() -> Path:
    value = os.environ.get("ATHENA_HOME", "").strip()
    return Path(value).expanduser().resolve() if value else (Path.home() / ".athena").resolve()


def binding_path() -> Path:
    return _home() / "bindings.yaml"


def _read() -> dict[str, Any]:
    path = binding_path()
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {"version": 1, "bindings": []}
    except Exception:
        return {"version": 1, "bindings": []}
    if not isinstance(data, dict):
        return {"version": 1, "bindings": []}
    bindings = data.get("bindings")
    data["bindings"] = bindings if isinstance(bindings, list) else []
    data.setdefault("version", 1)
    return data


def _write(data: dict[str, Any]) -> Path:
    import yaml

    path = binding_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".yaml.tmp")
    temp.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(temp, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def list_bindings() -> list[dict[str, Any]]:
    return [dict(item) for item in _read()["bindings"] if isinstance(item, dict)]


def add_binding(
    agent: str,
    platform: str,
    *,
    user_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    scope_id: Optional[str] = None,
    chat_type: Optional[str] = None,
    name: Optional[str] = None,
) -> dict[str, Any]:
    from athena.agents import get_agent

    agent_id = str(agent).strip().lower()
    if get_agent(agent_id) is None:
        raise ValueError(f"Athena agent {agent_id!r} does not exist")
    platform_id = str(platform).strip().lower()
    if not platform_id:
        raise ValueError("platform is required")
    if not any((user_id, chat_id, thread_id, scope_id, chat_type)):
        raise ValueError("binding needs at least one peer discriminator")

    entry = {
        "id": uuid.uuid4().hex[:10],
        "name": name or f"{agent_id}-{platform_id}",
        "agent": agent_id,
        "platform": platform_id,
        "user_id": str(user_id) if user_id else None,
        "chat_id": str(chat_id) if chat_id else None,
        "thread_id": str(thread_id) if thread_id else None,
        "scope_id": str(scope_id) if scope_id else None,
        "chat_type": str(chat_type) if chat_type else None,
        "enabled": True,
        "created_at": time.time(),
    }
    entry = {key: value for key, value in entry.items() if value is not None}
    data = _read()
    identity = tuple(entry.get(key) for key in (
        "platform", "user_id", "chat_id", "thread_id", "scope_id", "chat_type"
    ))
    for current in data["bindings"]:
        if not isinstance(current, dict):
            continue
        current_identity = tuple(current.get(key) for key in (
            "platform", "user_id", "chat_id", "thread_id", "scope_id", "chat_type"
        ))
        if identity == current_identity and current.get("enabled", True):
            raise ValueError(
                f"binding conflicts with {current.get('id')} routed to {current.get('agent')}"
            )
    data["bindings"].append(entry)
    _write(data)
    return entry


def remove_binding(binding_id: str) -> bool:
    data = _read()
    before = len(data["bindings"])
    data["bindings"] = [
        item for item in data["bindings"]
        if not isinstance(item, dict) or str(item.get("id")) != str(binding_id)
    ]
    if len(data["bindings"]) == before:
        return False
    _write(data)
    return True


def routing_entries() -> list[dict[str, Any]]:
    """Return bindings in the raw shape consumed by Athena profile routing."""

    routes = []
    for item in list_bindings():
        if not item.get("enabled", True):
            continue
        routes.append({
            "name": f"athena:{item.get('id')}",
            "platform": item.get("platform"),
            "profile": item.get("agent"),
            "guild_id": item.get("scope_id"),
            "chat_id": item.get("chat_id"),
            "thread_id": item.get("thread_id"),
            "user_id": item.get("user_id"),
            "chat_type": item.get("chat_type"),
            "enabled": item.get("enabled", True),
        })
    return routes

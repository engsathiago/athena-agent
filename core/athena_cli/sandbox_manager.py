"""Lifecycle manager for Athena-owned disposable execution environments.

The terminal backends create a sandbox for a single agent session.  This
module adds the missing product-level lifecycle: named environments that can
be created, inspected, stopped, restarted, snapshotted and removed from the
dashboard.  Docker is the first fully managed driver because it is available
on a plain VPS and already is Athena's default isolation substrate.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from athena_constants import get_athena_home


_LOCK = threading.RLock()
_SAFE_NAME = re.compile(r"[^a-z0-9_.-]+")
_DEFAULT_IMAGE = "nikolaik/python-nodejs:python3.11-nodejs20"


def _limits() -> dict[str, float | int]:
    defaults: dict[str, float | int] = {
        "max_running": 8,
        "max_total_cpu": 16.0,
        "max_total_memory_mb": 32_768,
    }
    try:
        from athena_cli.config import load_config

        configured = load_config().get("environments") or {}
        if isinstance(configured, dict):
            defaults["max_running"] = max(1, int(configured.get("max_running", defaults["max_running"])))
            defaults["max_total_cpu"] = max(0.1, float(configured.get("max_total_cpu", defaults["max_total_cpu"])))
            defaults["max_total_memory_mb"] = max(128, int(configured.get("max_total_memory_mb", defaults["max_total_memory_mb"])))
    except Exception:
        pass
    return defaults


def _root() -> Path:
    path = get_athena_home() / "platform" / "sandboxes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path() -> Path:
    return _root() / "registry.json"


def _load() -> dict[str, dict[str, Any]]:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _save(items: dict[str, dict[str, Any]]) -> None:
    path = _state_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _docker() -> str:
    import shutil

    executable = shutil.which("docker")
    if not executable:
        for candidate in (
            "/usr/local/bin/docker", "/opt/homebrew/bin/docker",
            "/Applications/Docker.app/Contents/Resources/bin/docker",
        ):
            if Path(candidate).is_file():
                executable = candidate
                break
    if not executable:
        raise RuntimeError("Docker não foi encontrado nesta máquina")
    return executable


def _run(args: list[str], *, timeout: float = 90) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [_docker(), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "erro desconhecido").strip()
        raise RuntimeError(detail[:2000])
    return result


def capabilities() -> dict[str, Any]:
    available = False
    error = ""
    try:
        result = _run(["version", "--format", "{{.Server.Version}}"], timeout=8)
        available = bool(result.stdout.strip())
    except Exception as exc:
        error = str(exc)
    return {
        "drivers": [
            {
                "id": "docker",
                "name": "Docker local/VPS",
                "available": available,
                "managed": True,
                "description": "Ambiente descartável ou persistente executado nesta máquina.",
                "error": error,
            },
            {
                "id": "modal",
                "name": "Modal Cloud",
                "available": True,
                "managed": False,
                "description": "Disponível como backend automático das sessões Athena.",
            },
            {
                "id": "vercel_sandbox",
                "name": "Vercel Sandbox",
                "available": True,
                "managed": False,
                "description": "Disponível como backend automático com snapshots.",
            },
        ],
        "default_image": _DEFAULT_IMAGE,
    }


def _slug(value: str) -> str:
    slug = _SAFE_NAME.sub("-", value.strip().lower()).strip("-.")
    return (slug or "ambiente")[:40]


def _inspect(record: dict[str, Any]) -> dict[str, Any]:
    container_id = str(record.get("container_id") or "")
    if not container_id:
        return record
    try:
        result = _run(
            ["inspect", "--format", "{{json .State}}", container_id], timeout=8
        )
        state = json.loads(result.stdout or "{}")
        if state.get("Running"):
            record["status"] = "running"
        elif state.get("Paused"):
            record["status"] = "paused"
        elif state.get("Dead"):
            record["status"] = "failed"
        else:
            record["status"] = "stopped"
        record["exit_code"] = state.get("ExitCode")
        record["runtime_error"] = state.get("Error") or ""
    except Exception:
        if record.get("status") not in {"deleted", "expired"}:
            record["status"] = "missing"
    expires_at = float(record.get("expires_at") or 0)
    if expires_at and expires_at <= time.time() and record.get("status") == "running":
        record["expired"] = True
    else:
        record["expired"] = False
    return record


def list_environments() -> dict[str, Any]:
    # A dashboard request is also an immediate reconciliation point.  The web
    # server runs the same sweep periodically, so expiry still works while no
    # browser is open.
    sweep_expired()
    with _LOCK:
        items = _load()
        changed = False
        environments = []
        for key in sorted(items, key=lambda item: items[item].get("created_at", 0), reverse=True):
            before = json.dumps(items[key], sort_keys=True)
            environments.append(_inspect(items[key]))
            changed = changed or before != json.dumps(items[key], sort_keys=True)
        if changed:
            _save(items)
    counts: dict[str, int] = {}
    for item in environments:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {"environments": environments, "counts": counts, "limits": _limits(), **capabilities()}


def create_environment(
    *,
    name: str,
    image: str = _DEFAULT_IMAGE,
    ttl_minutes: int = 120,
    cpu: float = 1,
    memory_mb: int = 1024,
    persistent: bool = False,
    network: bool = False,
) -> dict[str, Any]:
    if not image.strip():
        raise ValueError("a imagem Docker é obrigatória")
    ttl_minutes = min(max(int(ttl_minutes), 5), 7 * 24 * 60)
    cpu = min(max(float(cpu), 0.1), 64)
    memory_mb = min(max(int(memory_mb), 128), 262_144)
    environment_id = f"env_{uuid.uuid4().hex[:16]}"
    container_name = f"athena-{_slug(name)}-{environment_id[-6:]}"
    workspace = _root() / environment_id / "workspace"

    args = [
        "run", "-d", "--name", container_name,
        "--label", "athena.managed=true",
        "--label", f"athena.environment={environment_id}",
        "--security-opt", "no-new-privileges",
        "--cap-drop", "ALL",
        "--pids-limit", "512",
        "--cpus", str(cpu),
        "--memory", f"{memory_mb}m",
        "--shm-size", "512m",
    ]
    if not network:
        args.extend(["--network", "none"])
    if persistent:
        workspace.mkdir(parents=True, exist_ok=True)
        args.extend(["-v", f"{workspace}:/workspace"])
    else:
        args.extend(["--tmpfs", "/workspace:rw,exec,size=10g"])
    args.extend([image.strip(), "sleep", "infinity"])

    with _LOCK:
        items = _load()
        active = [_inspect(item) for item in items.values()]
        running = [item for item in active if item.get("status") == "running"]
        limits = _limits()
        if len(running) >= int(limits["max_running"]):
            raise RuntimeError("limite de ambientes simultâneos atingido")
        used_cpu = sum(float(item.get("cpu") or 0) for item in running)
        used_memory = sum(int(item.get("memory_mb") or 0) for item in running)
        if used_cpu + cpu > float(limits["max_total_cpu"]):
            raise RuntimeError("a criação excederia o limite total de processador")
        if used_memory + memory_mb > int(limits["max_total_memory_mb"]):
            raise RuntimeError("a criação excederia o limite total de memória")
        result = _run(args, timeout=180)
        now = time.time()
        record = {
            "id": environment_id,
            "name": name.strip() or "Novo ambiente",
            "backend": "docker",
            "container_id": result.stdout.strip(),
            "container_name": container_name,
            "image": image.strip(),
            "status": "running",
            "created_at": now,
            "updated_at": now,
            "expires_at": now + ttl_minutes * 60,
            "ttl_minutes": ttl_minutes,
            "cpu": cpu,
            "memory_mb": memory_mb,
            "persistent": bool(persistent),
            "network": bool(network),
            "workspace": str(workspace) if persistent else "",
            "snapshots": [],
        }
        items[environment_id] = record
        _save(items)
    return record


def _get(environment_id: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    items = _load()
    record = items.get(environment_id)
    if record is None:
        raise FileNotFoundError(f"ambiente não encontrado: {environment_id}")
    return items, record


def control(environment_id: str, action: str) -> dict[str, Any]:
    if action not in {"start", "stop", "restart"}:
        raise ValueError("ação inválida")
    with _LOCK:
        items, record = _get(environment_id)
        _run([action, str(record["container_id"])], timeout=60)
        record["status"] = "running" if action in {"start", "restart"} else "stopped"
        record["updated_at"] = time.time()
        record["expired"] = False
        _save(items)
        return _inspect(record)


def snapshot(environment_id: str, *, name: str = "") -> dict[str, Any]:
    with _LOCK:
        items, record = _get(environment_id)
        tag = _slug(name or f"{record['name']}-{int(time.time())}")
        image = f"athena-snapshot:{tag}"
        _run(["commit", str(record["container_id"]), image], timeout=300)
        snapshot_item = {"image": image, "created_at": time.time()}
        record.setdefault("snapshots", []).append(snapshot_item)
        record["updated_at"] = time.time()
        _save(items)
        return {"environment": record, "snapshot": snapshot_item}


def delete_environment(environment_id: str) -> dict[str, Any]:
    with _LOCK:
        items, record = _get(environment_id)
        try:
            _run(["rm", "-f", str(record["container_id"])], timeout=60)
        except RuntimeError as exc:
            if "No such container" not in str(exc):
                raise
        del items[environment_id]
        _save(items)
    return {"ok": True, "id": environment_id, "workspace_preserved": bool(record.get("persistent"))}


def sweep_expired() -> dict[str, Any]:
    stopped: list[str] = []
    now = time.time()
    with _LOCK:
        items = _load()
        for environment_id, record in items.items():
            if float(record.get("expires_at") or 0) > now:
                continue
            inspected = _inspect(record)
            if inspected.get("status") == "running":
                _run(["stop", str(record["container_id"])], timeout=60)
                record["status"] = "expired"
                record["updated_at"] = now
                stopped.append(environment_id)
        _save(items)
    return {"ok": True, "stopped": stopped, "count": len(stopped)}

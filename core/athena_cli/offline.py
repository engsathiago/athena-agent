"""Ollama-local readiness and portable offline bundle preparation."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from athena_constants import get_athena_home


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


def _ollama_root(base_url: str) -> str:
    value = str(base_url or DEFAULT_OLLAMA_URL).strip().rstrip("/")
    return value[:-3] if value.endswith("/v1") else value


def probe_ollama(base_url: str = DEFAULT_OLLAMA_URL, *, timeout: float = 0.5) -> dict[str, Any]:
    root = _ollama_root(base_url)
    models: list[str] = []
    error = None
    reachable = False
    try:
        with urllib.request.urlopen(f"{root}/api/tags", timeout=float(timeout)) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = [str(item.get("name")) for item in payload.get("models", []) if item.get("name")]
        reachable = True
    except (OSError, ValueError, urllib.error.URLError) as exc:
        error = str(exc)

    configured = False
    configured_model = None
    try:
        from athena_cli.config import load_config_readonly
        config = load_config_readonly()
        model = config.get("model") if isinstance(config.get("model"), dict) else {}
        configured_model = model.get("default")
        configured_url = str(model.get("base_url") or "")
        configured = model.get("provider") == "custom" and _ollama_root(configured_url) == root
    except Exception:
        pass

    disk = shutil.disk_usage(get_athena_home().parent)
    model_available = bool(
        configured_model
        and (
            configured_model in models
            or any(item.split(":", 1)[0] == str(configured_model) for item in models)
        )
    )
    return {
        "ready": bool(reachable and configured and model_available),
        "service_reachable": reachable,
        "ollama_command": shutil.which("ollama"),
        "base_url": root,
        "models": models,
        "configured_for_athena": configured,
        "configured_model": configured_model,
        "configured_model_available": model_available,
        "free_disk_bytes": disk.free,
        "error": error,
    }


def configure_ollama(model: str, *, base_url: str = DEFAULT_OLLAMA_URL, allow_missing: bool = False) -> dict[str, Any]:
    model = str(model or "").strip()
    if not model:
        raise ValueError("model is required")
    status = probe_ollama(base_url, timeout=1.5)
    if not status["service_reachable"] and not allow_missing:
        raise ValueError(f"Ollama is not reachable at {status['base_url']}")
    available = set(status["models"])
    if available and model not in available and not any(item.split(":", 1)[0] == model for item in available) and not allow_missing:
        raise ValueError(f"model is not installed in Ollama: {model}")

    from athena_cli.config import read_user_config_raw
    from utils import atomic_yaml_write
    config_path = get_athena_home() / "config.yaml"
    config = read_user_config_raw(config_path)
    model_config = config.setdefault("model", {})
    model_config.update({
        "default": model,
        "provider": "custom",
        "base_url": f"{_ollama_root(base_url)}/v1",
        "api_mode": "chat_completions",
    })
    config_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_yaml_write(config_path, config)
    return {"configured": True, "model": model, "base_url": model_config["base_url"], "config": str(config_path)}


def _source_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "core").is_dir():
            return parent
    return current.parents[2]


def _copy_source(source: Path, target: Path) -> None:
    excluded = {".git", ".venv", "venv", "node_modules", ".pnpm-store", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
    shutil.copytree(
        source,
        target,
        ignore=lambda _directory, names: [name for name in names if name in excluded or name.endswith(".pyc")],
    )


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_bundle(
    output: str | Path,
    *,
    source_root: str | Path | None = None,
    wheelhouse: str | Path | None = None,
    include_models: bool = False,
    ollama_models: str | Path | None = None,
    include_ollama: bool = False,
    ollama_binary: str | Path | None = None,
) -> dict[str, Any]:
    """Create a network-free install bundle from an online working machine."""

    destination = Path(output).expanduser().resolve()
    if destination.exists() and not destination.is_dir():
        raise FileExistsError(f"output path is not a directory: {destination}")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"output directory is not empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    source = Path(source_root).expanduser().resolve() if source_root else _source_root()
    if not source.is_dir():
        raise FileNotFoundError(f"Athena source not found: {source}")
    try:
        destination.relative_to(source)
    except ValueError:
        pass
    else:
        raise ValueError("offline bundle output must be outside the Athena source tree")
    _copy_source(source, destination / "athena-app")

    wheels_bundled = False
    if wheelhouse:
        wheels = Path(wheelhouse).expanduser().resolve()
        if not wheels.is_dir():
            raise FileNotFoundError(f"wheelhouse not found: {wheels}")
        shutil.copytree(wheels, destination / "wheels")
        wheels_bundled = True

    model_source = Path(ollama_models).expanduser() if ollama_models else Path.home() / ".ollama" / "models"
    models_bundled = False
    if include_models:
        if not model_source.is_dir():
            raise FileNotFoundError(f"Ollama model store not found: {model_source}")
        shutil.copytree(model_source, destination / "ollama-models")
        models_bundled = True

    ollama_bundled = False
    if include_ollama:
        executable_value = str(ollama_binary) if ollama_binary else shutil.which("ollama")
        if not executable_value:
            raise FileNotFoundError("Ollama executable was not found")
        executable = Path(executable_value).expanduser().resolve()
        if not executable.is_file():
            raise FileNotFoundError(f"Ollama executable not found: {executable}")
        bundle_bin = destination / "bin"
        bundle_bin.mkdir(parents=True, exist_ok=True)
        shutil.copy2(executable, bundle_bin / "ollama")
        os.chmod(bundle_bin / "ollama", 0o755)
        ollama_bundled = True

    installer_source = source / "install-offline.sh"
    if not installer_source.is_file():
        raise FileNotFoundError("install-offline.sh is missing from the Athena source")
    shutil.copy2(installer_source, destination / "install-offline.sh")
    os.chmod(destination / "install-offline.sh", 0o755)

    files = [path for path in destination.rglob("*") if path.is_file()]
    checksums = {str(path.relative_to(destination)): _checksum(path) for path in files}
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "source": str(source),
        "wheels_bundled": wheels_bundled,
        "ollama_models_bundled": models_bundled,
        "ollama_executable_bundled": ollama_bundled,
        "installation": "Run ./install-offline.sh inside this directory without internet.",
        "checksums": checksums,
    }
    manifest_path = destination / "offline-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"bundle": str(destination), "manifest": str(manifest_path), "files": len(files) + 1, "wheels_bundled": wheels_bundled, "ollama_models_bundled": models_bundled, "ollama_executable_bundled": ollama_bundled}

"""Versioned capability packages that combine skills, flows, and eval suites."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

import yaml

from athena_constants import get_athena_home


def builtin_root() -> Path:
    return Path(__file__).resolve().parents[1] / "work_packages"


def installed_root() -> Path:
    return get_athena_home() / "packages"


def _safe_name(value: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-.")
    if not name:
        raise ValueError("invalid package name")
    return name


def _resolve(source: str | Path) -> Path:
    path = Path(source).expanduser()
    if path.is_dir():
        return path.resolve()
    built_in = builtin_root() / _safe_name(str(source))
    if built_in.is_dir():
        return built_in
    raise FileNotFoundError(f"work package not found: {source}")


def _manifest(path: Path) -> dict[str, Any]:
    manifest_path = path / "athena-package.yaml"
    if not manifest_path.is_file():
        raise ValueError("package requires athena-package.yaml")
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("name") or not data.get("version"):
        raise ValueError("package manifest requires name and version")
    return data


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file() and not item.is_symlink():
            digest.update(str(item.relative_to(path)).encode())
            digest.update(item.read_bytes())
    return digest.hexdigest()


def _bundled_skill(name: str) -> Path | None:
    """Find a bundled Athena skill by its directory name."""
    root = Path(__file__).resolve().parents[1]
    matches: list[Path] = []
    for skills_root in (root / "skills", root / "optional-skills"):
        if not skills_root.is_dir():
            continue
        matches.extend(
            item.parent for item in skills_root.rglob("SKILL.md")
            if item.parent.name == name and item.parent.is_dir()
        )
    return sorted(matches)[0] if matches else None


def install(source: str | Path, *, force: bool = False) -> dict[str, Any]:
    package_dir = _resolve(source)
    manifest = _manifest(package_dir)
    name = _safe_name(str(manifest["name"]))
    target = installed_root() / name
    if target.exists() and not force:
        raise FileExistsError(f"package already installed: {name}")
    staging = installed_root() / f".{name}.staging-{os.getpid()}"
    staging.parent.mkdir(parents=True, exist_ok=True)
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(package_dir, staging, symlinks=False)
    digest = _tree_digest(staging)
    installed: dict[str, Any] = {"skills": [], "flows": [], "evals": []}
    rollback = installed_root() / f".{name}.rollback-{os.getpid()}"
    created_paths: list[Path] = []
    displaced_paths: list[tuple[Path, Path]] = []

    def copy_managed(source_path: Path, target_path: Path) -> bool:
        if target_path.exists():
            if not force:
                return False
            backup = rollback / str(len(displaced_paths))
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target_path), str(backup))
            displaced_paths.append((target_path, backup))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.is_dir():
            shutil.copytree(source_path, target_path)
        else:
            shutil.copy2(source_path, target_path)
        created_paths.append(target_path)
        return True

    try:
        # Validate every flow before touching the user's installation.
        from athena_cli.flows import _load_definition, install as install_flow

        flows_dir = staging / "flows"
        flow_files = sorted(flows_dir.glob("*.yaml")) if flows_dir.is_dir() else []
        for flow in flow_files:
            _load_definition(flow)

        skill_sources: dict[str, Path] = {}
        skills_dir = staging / "skills"
        if skills_dir.is_dir():
            for skill in sorted(skills_dir.iterdir()):
                if skill.is_dir() and (skill / "SKILL.md").is_file():
                    skill_sources[skill.name] = skill
        for skill_name in manifest.get("recommended_skills") or []:
            safe_skill = _safe_name(str(skill_name))
            bundled = _bundled_skill(safe_skill)
            if bundled is not None:
                skill_sources.setdefault(safe_skill, bundled)
        for skill_name, skill in sorted(skill_sources.items()):
            skill_target = get_athena_home() / "skills" / _safe_name(skill_name)
            if copy_managed(skill, skill_target):
                installed["skills"].append(str(skill_target))

        evals_dir = staging / "evals"
        if evals_dir.is_dir():
            eval_target = get_athena_home() / "evals" / "suites"
            eval_target.mkdir(parents=True, exist_ok=True)
            for suite in sorted(evals_dir.glob("*.jsonl")):
                copied = eval_target / f"{name}-{suite.name}"
                if copy_managed(suite, copied):
                    installed["evals"].append(str(copied))
        for flow in flow_files:
            installed["flows"].append(install_flow(flow))
        receipt = {
            "name": name, "version": str(manifest["version"]), "description": manifest.get("description", ""),
            "digest": digest, "source": str(package_dir), "installed_at": time.time(),
            "recommended_skills": list(manifest.get("recommended_skills") or []), **installed,
        }
        (staging / "installation.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        if target.exists():
            old = installed_root() / f".{name}.previous"
            if old.exists():
                shutil.rmtree(old)
            os.replace(target, old)
        os.replace(staging, target)
        if rollback.exists():
            shutil.rmtree(rollback)
        return receipt
    except Exception:
        for created in reversed(created_paths):
            if created.is_dir():
                shutil.rmtree(created)
            elif created.exists():
                created.unlink()
        for original, backup in reversed(displaced_paths):
            if backup.exists():
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(backup), str(original))
        if rollback.exists():
            shutil.rmtree(rollback)
        if staging.exists():
            shutil.rmtree(staging)
        raise


def list_packages() -> dict[str, Any]:
    available = []
    if builtin_root().is_dir():
        for path in sorted(builtin_root().iterdir()):
            try:
                data = _manifest(path)
                available.append({**data, "path": str(path)})
            except (OSError, ValueError):
                continue
    installed = []
    if installed_root().is_dir():
        for receipt in sorted(installed_root().glob("*/installation.json")):
            try:
                installed.append(json.loads(receipt.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return {"available": available, "installed": installed}

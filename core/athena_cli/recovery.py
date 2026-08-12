"""Backup discovery, verification and guarded restore orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from athena_constants import get_athena_home
from athena_cli.backup import create_quick_snapshot, run_import, verify_backup_archive


def list_archives(directory: str | Path | None = None) -> dict[str, Any]:
    roots = [Path(directory).expanduser()] if directory else [Path.home(), get_athena_home() / "backups"]
    seen: set[Path] = set()
    archives = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.glob("athena-backup-*.zip"):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                stat = resolved.stat()
            except OSError:
                continue
            archives.append({"path": str(resolved), "bytes": stat.st_size, "modified_at": stat.st_mtime})
    archives.sort(key=lambda item: item["modified_at"], reverse=True)
    return {"archives": archives, "latest": archives[0] if archives else None}


def restore_archive(path: str | Path, *, apply: bool = False) -> dict[str, Any]:
    verification = verify_backup_archive(path)
    if not verification["valid"]:
        return {"restored": False, "verification": verification, "error": "backup verification failed"}
    if not apply:
        return {"restored": False, "dry_run": True, "verification": verification}
    snapshot_id = create_quick_snapshot(label="pre-full-restore")
    run_import(SimpleNamespace(zipfile=str(Path(path).expanduser()), force=True))
    return {"restored": True, "pre_restore_snapshot": snapshot_id, "verification": verification}

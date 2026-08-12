"""``athena recovery`` command."""

from __future__ import annotations

import json
import sys


def cmd_recovery(args) -> int:
    from athena_cli import recovery

    try:
        action = args.recovery_action or "status"
        if action in {"status", "list"}:
            result = recovery.list_archives(args.directory)
        elif action == "verify":
            from athena_cli.backup import verify_backup_archive
            result = verify_backup_archive(args.archive)
        else:
            result = recovery.restore_archive(args.archive, apply=args.apply)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("valid", result.get("verification", {}).get("valid", True)) else 2
    except (OSError, TypeError, ValueError) as exc:
        print(f"recovery: {exc}", file=sys.stderr)
        return 2


def build_recovery_parser(subparsers) -> None:
    parser = subparsers.add_parser("recovery", help="Verify backups and restore with a safety snapshot")
    sub = parser.add_subparsers(dest="recovery_action")
    for name in ("status", "list"):
        item = sub.add_parser(name, help="List available full backups")
        item.add_argument("--directory")
    verify = sub.add_parser("verify", help="Check archive, CRC and SQLite integrity")
    verify.add_argument("archive")
    restore = sub.add_parser("restore", help="Verify and preview a restore")
    restore.add_argument("archive")
    restore.add_argument("--apply", action="store_true", help="Create a pre-restore snapshot and restore")
    parser.set_defaults(func=cmd_recovery)

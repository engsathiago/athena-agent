"""Athena bootstrap.

This module owns Athena's identity, state boundary and authorization policy,
then starts the vendored agent core through Athena's CLI.
"""

from __future__ import annotations

import os
import sys
import argparse
import json
import time
from pathlib import Path
from typing import Iterable


ATHENA_VERSION = "0.3.0"
_PACKAGE_DIR = Path(__file__).resolve().parent
_CORE_ROOT = _PACKAGE_DIR.parent
_TEMPLATE_DIR = _PACKAGE_DIR / "templates"


def get_athena_home() -> Path:
    """Return the state directory used by Athena.

    ``ATHENA_HOME`` is the public override used by the whole runtime, including
    profiles, sessions, skills, cron jobs, credentials and persistent memory.
    """

    configured = os.environ.get("ATHENA_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".athena").resolve()


def _write_if_missing(destination: Path, content: str) -> bool:
    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    try:
        destination.chmod(0o600)
    except OSError:
        pass
    return True


def _template_text(name: str) -> str:
    return (_TEMPLATE_DIR / name).read_text(encoding="utf-8")


def initialize_home(home: Path | None = None) -> list[Path]:
    """Create Athena's private state layout without overwriting user files."""

    target = home or get_athena_home()
    target.mkdir(parents=True, exist_ok=True)
    try:
        target.chmod(0o700)
    except OSError:
        pass

    for dirname in ("memories", "skills", "cron", "logs", "workspace", "profiles"):
        (target / dirname).mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    seeds = {
        target / "SOUL.md": _template_text("SOUL.md"),
        target / "memories" / "MEMORY.md": _template_text("MEMORY.md"),
        target / "memories" / "USER.md": _template_text("USER.md"),
        target / "config.yaml": _template_text("config.yaml"),
        target / "security.yaml": _template_text("security.yaml"),
        target / "HEARTBEAT.md": _template_text("HEARTBEAT.md"),
    }
    for destination, content in seeds.items():
        if _write_if_missing(destination, content):
            created.append(destination)
    manifest = target / "athena-agent.json"
    if not manifest.exists():
        payload = {
            "id": "default",
            "path": str(target),
            "description": "Athena primary personal agent",
            "created_at": time.time(),
            "source": "athena",
            "is_default": True,
        }
        if _write_if_missing(
            manifest,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        ):
            created.append(manifest)
    return created


def _handle_agent_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="athena agent")
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("list")
    create = sub.add_parser("create")
    create.add_argument("name")
    create.add_argument("--description", default="")
    create.add_argument("--clone-from", default="default")
    show = sub.add_parser("show")
    show.add_argument("name")
    use = sub.add_parser("use")
    use.add_argument("name")
    args = parser.parse_args(argv)

    from athena.agents import create_agent, get_agent, list_agents, use_agent

    if args.action in (None, "list"):
        agents = list_agents()
        print(f"{'Agent':<18} {'Type':<16} Description")
        for item in agents:
            kind = "primary" if item.is_default else item.source
            print(f"{item.id:<18} {kind:<16} {item.description or '—'}")
        return
    if args.action == "create":
        item = create_agent(
            args.name,
            description=args.description,
            clone_from=args.clone_from,
        )
        print(f"Created Athena agent {item.id} at {item.path}")
        return
    if args.action == "show":
        item = get_agent(args.name)
        if item is None:
            raise SystemExit(f"Athena agent {args.name!r} not found")
        print(json.dumps(item.__dict__, ensure_ascii=False, indent=2))
        return
    if args.action == "use":
        use_agent(args.name)
        print(f"Active Athena agent: {args.name}")


def _handle_binding_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="athena bind")
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("list")
    add = sub.add_parser("add")
    add.add_argument("agent")
    add.add_argument("--platform", required=True)
    add.add_argument("--user")
    add.add_argument("--chat")
    add.add_argument("--thread")
    add.add_argument("--scope")
    add.add_argument("--chat-type")
    add.add_argument("--name")
    remove = sub.add_parser("remove")
    remove.add_argument("binding_id")
    args = parser.parse_args(argv)

    from athena.bindings import add_binding, list_bindings, remove_binding

    if args.action in (None, "list"):
        print(json.dumps(list_bindings(), ensure_ascii=False, indent=2))
        return
    if args.action == "add":
        try:
            item = add_binding(
                args.agent,
                args.platform,
                user_id=args.user,
                chat_id=args.chat,
                thread_id=args.thread,
                scope_id=args.scope,
                chat_type=args.chat_type,
                name=args.name,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(item, ensure_ascii=False, indent=2))
        return
    if args.action == "remove":
        if not remove_binding(args.binding_id):
            raise SystemExit(f"Binding {args.binding_id!r} not found")
        print(f"Removed binding {args.binding_id}")


def _handle_heartbeat_command(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="athena heartbeat")
    sub = parser.add_subparsers(dest="action")
    status = sub.add_parser("status")
    status.add_argument("agent", nargs="?")
    enable = sub.add_parser("enable")
    enable.add_argument("agent")
    enable.add_argument("--every", default="30m")
    enable.add_argument("--deliver", default="local")
    enable.add_argument("--active-hours", default="08:00-22:00")
    disable = sub.add_parser("disable")
    disable.add_argument("agent")
    args = parser.parse_args(argv)

    from athena.heartbeat import disable_heartbeat, enable_heartbeat, heartbeat_status

    if args.action in (None, "status"):
        print(json.dumps(heartbeat_status(getattr(args, "agent", None)), ensure_ascii=False, indent=2))
        return
    if args.action == "enable":
        schedule = args.every if str(args.every).lower().startswith("every ") else f"every {args.every}"
        record = enable_heartbeat(
            args.agent,
            schedule=schedule,
            deliver=args.deliver,
            active_hours=args.active_hours,
        )
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return
    if args.action == "disable":
        if not disable_heartbeat(args.agent):
            raise SystemExit(f"No heartbeat configured for {args.agent!r}")
        print(f"Heartbeat disabled for {args.agent}")


def _activate_runtime(home: Path) -> None:
    if sys.version_info < (3, 11) or sys.version_info >= (3, 14):
        detected = ".".join(str(part) for part in sys.version_info[:3])
        raise SystemExit(
            "Athena requires Python 3.11, 3.12, or 3.13 "
            f"(detected {detected}). Run install.sh again or set "
            "ATHENA_PYTHON to a supported executable."
        )
    if not (_CORE_ROOT / "athena_cli").is_dir():
        raise RuntimeError(f"Athena core not found at {_CORE_ROOT}")

    os.environ["ATHENA_HOME"] = str(home)
    os.environ["ATHENA_RUNTIME"] = "1"
    os.environ["ATHENA_BRAND"] = "1"
    os.environ.setdefault("ATHENA_ENVIRONMENT_HINT", "Athena personal agent runtime")

    # Compatibility flags cover older/indirect Athena paths that do not yet
    # call the bridge themselves. They are derived from Athena's authority,
    # not independently configurable security decisions.
    try:
        from athena.security import load_policy

        if load_policy(refresh=True).get("mode") == "unrestricted":
            os.environ["ATHENA_YOLO_MODE"] = "1"
            os.environ["ATHENA_ALLOW_PRIVATE_URLS"] = "true"
            os.environ["ATHENA_REDACT_SECRETS"] = "false"
    except Exception:
        pass

    athena_path = str(_CORE_ROOT)
    if athena_path not in sys.path:
        sys.path.insert(0, athena_path)


def _print_init_result(home: Path, created: Iterable[Path]) -> None:
    created = list(created)
    print(f"Athena home: {home}")
    if created:
        print("Created:")
        for path in created:
            print(f"  - {path.relative_to(home)}")
    else:
        print("Athena was already initialized; no files were overwritten.")


def main() -> None:
    """Initialize Athena when needed, then start Athena's CLI."""

    home = get_athena_home()
    command = sys.argv[1] if len(sys.argv) > 1 else ""

    if command in {"--athena-version", "athena-version"}:
        print(f"Athena {ATHENA_VERSION}")
        return

    created = initialize_home(home)
    if command == "init":
        _print_init_result(home, created)
        return

    _activate_runtime(home)

    if command == "security":
        from athena.security import VALID_MODES, get_policy_path, load_policy, set_mode

        action = sys.argv[2].strip().lower() if len(sys.argv) > 2 else "status"
        if action == "status":
            policy = load_policy(refresh=True)
            print(f"Athena security mode: {policy['mode']}")
            print(f"Policy: {get_policy_path()}")
            print(f"Default in controlled mode: {policy['default']}")
            print(f"Owner rules: {len(policy.get('rules', []))}")
            return
        if action == "mode" and len(sys.argv) > 3:
            mode = sys.argv[3].strip().lower()
            try:
                path = set_mode(mode)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            print(f"Athena security mode set to {mode} in {path}")
            return
        choices = "|".join(VALID_MODES)
        raise SystemExit(
            "Usage: athena security status | "
            f"athena security mode <{choices}>"
        )

    if command == "agent":
        _handle_agent_command(sys.argv[2:])
        return
    if command in {"bind", "binding", "bindings"}:
        _handle_binding_command(sys.argv[2:])
        return
    if command == "heartbeat":
        _handle_heartbeat_command(sys.argv[2:])
        return

    # Preserve the mature core parser and every existing command while keeping
    # Athena as the only public entrypoint.
    sys.argv[0] = "athena"
    from athena_cli.main import main as athena_main

    athena_main()

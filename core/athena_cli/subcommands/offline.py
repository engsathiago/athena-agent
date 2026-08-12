"""``athena offline`` command."""

from __future__ import annotations

import json
import sys


def cmd_offline(args) -> int:
    from athena_cli import offline

    try:
        action = args.offline_action or "status"
        if action == "configure":
            result = offline.configure_ollama(args.model, base_url=args.base_url, allow_missing=args.allow_missing)
        elif action == "prepare":
            result = offline.prepare_bundle(args.output, source_root=args.source_root, wheelhouse=args.wheelhouse, include_models=args.include_models, ollama_models=args.ollama_models, include_ollama=args.include_ollama, ollama_binary=args.ollama_binary)
        else:
            result = offline.probe_ollama(args.base_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, TypeError, ValueError) as exc:
        print(f"offline: {exc}", file=sys.stderr)
        return 2


def build_offline_parser(subparsers) -> None:
    parser = subparsers.add_parser("offline", help="Prepare and run Athena with local Ollama")
    sub = parser.add_subparsers(dest="offline_action")
    status = sub.add_parser("status", help="Check Ollama and offline readiness")
    status.add_argument("--base-url", default="http://127.0.0.1:11434")
    configure = sub.add_parser("configure", help="Use an installed Ollama model")
    configure.add_argument("--model", required=True)
    configure.add_argument("--base-url", default="http://127.0.0.1:11434")
    configure.add_argument("--allow-missing", action="store_true", help="Write config even when the service/model is not currently available")
    prepare = sub.add_parser("prepare", help="Build a portable, network-free installer directory")
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--source-root")
    prepare.add_argument("--wheelhouse", help="Directory containing all Python wheels for offline install")
    prepare.add_argument("--include-models", action="store_true", help="Copy the local Ollama model store (can be very large)")
    prepare.add_argument("--ollama-models", help="Override the Ollama model-store directory")
    prepare.add_argument("--include-ollama", action="store_true", help="Copy the Ollama executable for the same operating system and architecture")
    prepare.add_argument("--ollama-binary", help="Override the Ollama executable path")
    parser.set_defaults(func=cmd_offline)

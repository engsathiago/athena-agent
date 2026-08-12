"""``athena evolve`` command."""

from __future__ import annotations

import json
import sys


def cmd_evolve(args) -> int:
    from athena_cli import evolution

    try:
        action = args.evolve_action or "status"
        if action == "propose":
            result = evolution.propose(args.source, name=args.name, reason=args.reason)
        elif action == "evaluate":
            result = evolution.evaluate(args.proposal, args.report, min_score=args.min_score)
        elif action == "activate":
            result = evolution.activate(args.proposal)
        elif action == "rollback":
            result = evolution.rollback(args.proposal)
        elif action == "signals":
            result = evolution.inspect_signals(limit=args.limit)
        else:
            result = evolution.status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"evolve: {exc}", file=sys.stderr)
        return 2


def build_evolve_parser(subparsers) -> None:
    parser = subparsers.add_parser("evolve", help="Propose, test, activate and roll back skills")
    sub = parser.add_subparsers(dest="evolve_action")
    propose = sub.add_parser("propose", help="Stage a skill as a reviewable proposal")
    propose.add_argument("source")
    propose.add_argument("--name")
    propose.add_argument("--reason", default="")
    evaluate = sub.add_parser("evaluate", help="Attach an evaluation report and decide")
    evaluate.add_argument("proposal")
    evaluate.add_argument("report")
    evaluate.add_argument("--min-score", type=float, default=0.8)
    activate = sub.add_parser("activate", help="Activate an accepted skill proposal")
    activate.add_argument("proposal")
    rollback = sub.add_parser("rollback", help="Restore the skill version from before activation")
    rollback.add_argument("proposal")
    signals = sub.add_parser("signals", help="Inspect recent repeated evaluation and task failures")
    signals.add_argument("--limit", type=int, default=20)
    sub.add_parser("status", help="Show proposal history")
    parser.set_defaults(func=cmd_evolve)

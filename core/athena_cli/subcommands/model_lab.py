"""``athena model-lab`` parser and command handler."""

from __future__ import annotations

import json
import sys


def _required_metrics(values: list[str]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for value in values:
        name, separator, minimum = value.partition("=")
        if not separator or not name.strip():
            raise ValueError(f"invalid required metric {value!r}; use name=minimum")
        parsed[name.strip()] = float(minimum)
    return parsed


def cmd_model_lab(args) -> int:
    from athena_cli import model_lab

    try:
        action = args.model_lab_action
        if action == "dataset":
            result = model_lab.prepare_dataset(args.input, name=args.name)
        elif action == "compare":
            result = model_lab.compare_models(
                args.baseline,
                args.candidate,
                candidate_name=args.name,
                max_regression=args.max_regression,
                min_improvement=args.min_improvement,
                required=_required_metrics(args.require),
            )
        elif action == "register":
            result = model_lab.register_candidate(
                args.name, args.model_ref, evaluation=args.evaluation
            )
        elif action == "activate":
            result = model_lab.activate_candidate(
                args.name, allow_unverified=args.allow_unverified
            )
        elif action == "rollback":
            result = model_lab.rollback_candidate()
        else:
            result = model_lab.lab_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"model-lab: {exc}", file=sys.stderr)
        return 2


def build_model_lab_parser(subparsers) -> None:
    parser = subparsers.add_parser(
        "model-lab",
        help="Prepare and safely evaluate local model candidates",
    )
    sub = parser.add_subparsers(dest="model_lab_action")

    dataset = sub.add_parser("dataset", help="Clean and freeze a training JSONL")
    dataset.add_argument("--input", required=True)
    dataset.add_argument("--name", default="dataset")

    compare = sub.add_parser("compare", help="Compare baseline and candidate metrics")
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--name", required=True)
    compare.add_argument("--max-regression", type=float, default=0.02)
    compare.add_argument("--min-improvement", type=float, default=0.0)
    compare.add_argument(
        "--require", action="append", default=[], metavar="METRIC=MINIMUM"
    )

    register = sub.add_parser("register", help="Register a local model candidate")
    register.add_argument("name")
    register.add_argument("model_ref")
    register.add_argument("--evaluation")

    activate = sub.add_parser("activate", help="Activate an accepted lab candidate")
    activate.add_argument("name")
    activate.add_argument(
        "--allow-unverified",
        action="store_true",
        help="Explicitly bypass the evaluation gate for isolated experiments",
    )

    sub.add_parser("rollback", help="Return to the previously active candidate")
    sub.add_parser("status", help="Show candidates and current lab activation")
    parser.set_defaults(func=cmd_model_lab)

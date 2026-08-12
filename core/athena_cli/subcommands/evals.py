"""``athena evals`` command."""

from __future__ import annotations

import json
import sys


def cmd_evals(args) -> int:
    from athena_cli import eval_suite

    try:
        action = args.evals_action or "status"
        if action == "init":
            result = eval_suite.init_suite(args.name, count=args.count, overwrite=args.force)
        elif action == "run":
            result = eval_suite.run_suite(args.suite, repetitions=args.repetitions, timeout=args.timeout)
        elif action == "compare":
            result = eval_suite.compare_reports(args.baseline, args.candidate, max_regression=args.max_regression, min_improvement=args.min_improvement)
        elif action == "import-traces":
            result = eval_suite.import_traces(args.name, limit=args.limit, include_failed=not args.only_success)
        elif action == "ci":
            result = eval_suite.ci_gate(
                args.suite, min_score=args.min_score, max_latency_seconds=args.max_latency,
                baseline=args.baseline, max_regression=args.max_regression,
                repetitions=args.repetitions, timeout=args.timeout,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["accepted"] else 1
        else:
            result = eval_suite.status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"evals: {exc}", file=sys.stderr)
        return 2


def build_evals_parser(subparsers) -> None:
    parser = subparsers.add_parser("evals", help="Run repeatable quality evaluations")
    sub = parser.add_subparsers(dest="evals_action")
    init = sub.add_parser("init", help="Create the editable starter suite")
    init.add_argument("--name", default="starter")
    init.add_argument("--count", type=int, default=30)
    init.add_argument("--force", action="store_true")
    run = sub.add_parser("run", help="Run a suite through the real Athena agent")
    run.add_argument("suite")
    run.add_argument("--repetitions", type=int, default=1)
    run.add_argument("--timeout", type=float, default=120.0)
    compare = sub.add_parser("compare", help="Compare baseline and candidate reports")
    compare.add_argument("baseline")
    compare.add_argument("candidate")
    compare.add_argument("--max-regression", type=float, default=0.02)
    compare.add_argument("--min-improvement", type=float, default=0.0)
    imported = sub.add_parser("import-traces", help="Create a regression suite from real local traces")
    imported.add_argument("--name", default="real-trajectories")
    imported.add_argument("--limit", type=int, default=50)
    imported.add_argument("--only-success", action="store_true")
    ci = sub.add_parser("ci", help="Run a quality gate suitable for CI/CD")
    ci.add_argument("suite")
    ci.add_argument("--min-score", type=float, default=0.9)
    ci.add_argument("--max-latency", type=float)
    ci.add_argument("--baseline")
    ci.add_argument("--max-regression", type=float, default=0.02)
    ci.add_argument("--repetitions", type=int, default=1)
    ci.add_argument("--timeout", type=float, default=120.0)
    sub.add_parser("status", help="Show suites and the latest result")
    parser.set_defaults(func=cmd_evals)

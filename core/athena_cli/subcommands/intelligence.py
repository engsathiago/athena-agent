"""CLI surfaces for Athena's operational intelligence platform."""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import uuid
from pathlib import Path


def _print(value) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def _load_json(value: str | None) -> dict:
    if not value:
        return {}
    path = Path(value).expanduser()
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(value)


def cmd_traces(args) -> int:
    from athena_cli import trace_studio
    action = args.trace_action or "status"
    if action == "list":
        return _print(trace_studio.list_runs(limit=args.limit, status=args.status))
    if action == "show":
        return _print(trace_studio.get_run(args.id))
    if action == "replay":
        return _print(trace_studio.replay_manifest(args.id))
    if action == "prune":
        return _print(trace_studio.prune(
            max_age_days=args.days, keep_latest=args.keep, execute=args.execute,
        ))
    return _print(trace_studio.status())


def cmd_results(args) -> int:
    from athena_cli import result_hub
    action = args.results_action or "status"
    if action == "list":
        return _print(result_hub.list_items(status=args.status, limit=args.limit))
    if action == "show":
        return _print(result_hub.get_item(args.id))
    if action in {"approve", "changes", "archive"}:
        status = {"approve": "approved", "changes": "changes_requested", "archive": "archived"}[action]
        return _print(result_hub.update_status(args.id, status, note=args.note))
    if action == "add-artifact":
        return _print(result_hub.add_artifact(args.id, args.path, name=args.name))
    return _print(result_hub.status())


def cmd_flows(args) -> int:
    from athena_cli import flows
    action = args.flows_action or "status"
    if action == "init":
        target = Path(args.path).expanduser()
        if target.exists() and not args.force:
            raise FileExistsError(target)
        import yaml
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(flows.starter_definition(), allow_unicode=True, sort_keys=False), encoding="utf-8")
        return _print({"path": str(target.resolve())})
    if action == "install":
        return _print(flows.install(args.source))
    if action == "start":
        run = flows.start(args.flow, _load_json(args.input))
        return _print(flows.run(run["id"], max_parallel=args.max_parallel) if not args.no_run else run)
    if action == "resume":
        value = json.loads(args.value) if args.value else None
        return _print(flows.resume(args.id, step_id=args.step, value=value, max_parallel=args.max_parallel))
    if action == "retry":
        return _print(flows.retry(args.id, args.step))
    if action == "fork":
        return _print(flows.fork(args.id, from_step=args.step))
    if action == "show":
        return _print(flows.get_run(args.id))
    return _print(flows.status())


def cmd_router(args) -> int:
    from athena_cli import adaptive_router
    action = args.router_action or "status"
    if action == "recommend":
        return _print(adaptive_router.recommend(args.prompt, current_model=args.model, current_provider=args.provider))
    return _print(adaptive_router.status())


def cmd_experiments(args) -> int:
    from athena_cli import experiments
    action = args.experiment_action or "status"
    if action == "create":
        return _print(experiments.create(
            args.name, kind=args.kind, baseline=args.baseline, candidate=args.candidate,
            traffic_percent=args.traffic, min_samples=args.min_samples, max_regression=args.max_regression,
        ))
    if action in {"start", "pause"}:
        return _print(experiments.set_status(args.id, "running" if action == "start" else "paused"))
    if action == "assign":
        return _print(experiments.assign(args.id, args.subject))
    if action == "record":
        return _print(experiments.record(args.id, args.variant, args.score))
    if action == "show":
        return _print(experiments.evaluate(args.id))
    return _print(experiments.status())


def cmd_packages(args) -> int:
    from athena_cli import work_packages
    action = args.package_action or "list"
    if action == "install":
        return _print(work_packages.install(args.source, force=args.force))
    return _print(work_packages.list_packages())


def cmd_workers(args) -> int:
    from athena_cli import distributed_workers as workers
    action = args.workers_action or "status"
    if action == "register":
        return _print(workers.register_node(
            args.id, name=args.name or args.id, labels=args.label,
            capabilities=args.capability, max_jobs=args.max_jobs,
        ))
    if action == "submit":
        payload = _load_json(args.payload)
        return _print(workers.submit(args.kind, payload, requirements=args.require, priority=args.priority))
    if action == "show":
        return _print(workers.get_job(args.id))
    if action == "work-once":
        return _print(workers.work_once(args.id))
    if action == "serve":
        token = os.environ.get(args.token_env, "") if args.token_env else ""
        workers.serve_controller(bind=args.bind, port=args.port, token=token)
        return 0
    if action == "connect":
        token = os.environ.get(args.token_env, "") if args.token_env else ""
        node_id = args.id or f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
        result = workers.run_remote_worker(
            args.controller, node_id=node_id, name=args.name or socket.gethostname(),
            token=token, labels=args.label, capabilities=args.capability,
            poll_seconds=args.poll, once=args.once,
        )
        return _print(result)
    return _print(workers.status())


def build_intelligence_parsers(subparsers) -> None:
    traces = subparsers.add_parser("traces", help="Inspect end-to-end agent traces")
    sub = traces.add_subparsers(dest="trace_action")
    sub.add_parser("status")
    listing = sub.add_parser("list"); listing.add_argument("--limit", type=int, default=50); listing.add_argument("--status")
    show = sub.add_parser("show"); show.add_argument("id")
    replay = sub.add_parser("replay"); replay.add_argument("id")
    prune = sub.add_parser("prune"); prune.add_argument("--days", type=int, default=30); prune.add_argument("--keep", type=int, default=5000); prune.add_argument("--execute", action="store_true")
    traces.set_defaults(func=cmd_traces)

    results = subparsers.add_parser("results", help="Review completed work and artifacts")
    sub = results.add_subparsers(dest="results_action")
    sub.add_parser("status")
    listing = sub.add_parser("list"); listing.add_argument("--status"); listing.add_argument("--limit", type=int, default=100)
    show = sub.add_parser("show"); show.add_argument("id")
    for name in ("approve", "changes", "archive"):
        action = sub.add_parser(name); action.add_argument("id"); action.add_argument("--note", default="")
    artifact = sub.add_parser("add-artifact"); artifact.add_argument("id"); artifact.add_argument("path"); artifact.add_argument("--name")
    results.set_defaults(func=cmd_results)

    flows = subparsers.add_parser("flows", help="Run durable and resumable workflows")
    sub = flows.add_subparsers(dest="flows_action")
    sub.add_parser("status")
    init = sub.add_parser("init"); init.add_argument("path", nargs="?", default="athena-flow.yaml"); init.add_argument("--force", action="store_true")
    install = sub.add_parser("install"); install.add_argument("source")
    start = sub.add_parser("start"); start.add_argument("flow"); start.add_argument("--input"); start.add_argument("--max-parallel", type=int, default=4); start.add_argument("--no-run", action="store_true")
    resume = sub.add_parser("resume"); resume.add_argument("id"); resume.add_argument("--step"); resume.add_argument("--value"); resume.add_argument("--max-parallel", type=int, default=4)
    retry = sub.add_parser("retry"); retry.add_argument("id"); retry.add_argument("step")
    fork = sub.add_parser("fork"); fork.add_argument("id"); fork.add_argument("step")
    show = sub.add_parser("show"); show.add_argument("id")
    flows.set_defaults(func=cmd_flows)

    router = subparsers.add_parser("router", help="Inspect adaptive model routing")
    sub = router.add_subparsers(dest="router_action"); sub.add_parser("status")
    recommend = sub.add_parser("recommend"); recommend.add_argument("prompt"); recommend.add_argument("--model", required=True); recommend.add_argument("--provider", default="")
    router.set_defaults(func=cmd_router)

    experiments = subparsers.add_parser("experiments", help="Manage canary experiments")
    sub = experiments.add_subparsers(dest="experiment_action"); sub.add_parser("status")
    create = sub.add_parser("create"); create.add_argument("name"); create.add_argument("--kind", required=True); create.add_argument("--baseline", required=True); create.add_argument("--candidate", required=True); create.add_argument("--traffic", type=float, default=5); create.add_argument("--min-samples", type=int, default=20); create.add_argument("--max-regression", type=float, default=.02)
    for name in ("start", "pause", "show"):
        action = sub.add_parser(name); action.add_argument("id")
    assign = sub.add_parser("assign"); assign.add_argument("id"); assign.add_argument("subject")
    record = sub.add_parser("record"); record.add_argument("id"); record.add_argument("variant", choices=("baseline", "candidate")); record.add_argument("score", type=float)
    experiments.set_defaults(func=cmd_experiments)

    packages = subparsers.add_parser("packages", help="Install complete Athena capability packages")
    sub = packages.add_subparsers(dest="package_action"); sub.add_parser("list")
    install = sub.add_parser("install"); install.add_argument("source"); install.add_argument("--force", action="store_true")
    packages.set_defaults(func=cmd_packages)

    workers = subparsers.add_parser("workers", help="Manage local and multi-VPS workers")
    sub = workers.add_subparsers(dest="workers_action"); sub.add_parser("status")
    register = sub.add_parser("register"); register.add_argument("id"); register.add_argument("--name"); register.add_argument("--label", action="append", default=[]); register.add_argument("--capability", action="append", default=[]); register.add_argument("--max-jobs", type=int, default=1)
    submit = sub.add_parser("submit"); submit.add_argument("kind", choices=("athena", "command", "flow")); submit.add_argument("payload"); submit.add_argument("--require", action="append", default=[]); submit.add_argument("--priority", type=int, default=0)
    show = sub.add_parser("show"); show.add_argument("id")
    once = sub.add_parser("work-once"); once.add_argument("id")
    serve = sub.add_parser("serve"); serve.add_argument("--bind", default="127.0.0.1"); serve.add_argument("--port", type=int, default=9121); serve.add_argument("--token-env", default="ATHENA_WORKER_TOKEN")
    connect = sub.add_parser("connect"); connect.add_argument("controller"); connect.add_argument("--id"); connect.add_argument("--name"); connect.add_argument("--label", action="append", default=[]); connect.add_argument("--capability", action="append", default=[]); connect.add_argument("--poll", type=float, default=3); connect.add_argument("--once", action="store_true"); connect.add_argument("--token-env", default="ATHENA_WORKER_TOKEN")
    workers.set_defaults(func=cmd_workers)

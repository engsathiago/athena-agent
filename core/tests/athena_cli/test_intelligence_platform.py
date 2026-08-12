from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path


def _reset_db() -> None:
    from athena_cli.intelligence_db import reset_schema_cache_for_tests

    reset_schema_cache_for_tests()


def test_trace_studio_captures_full_lifecycle_and_creates_review_item(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / ".athena"))
    _reset_db()
    from athena_cli import trace_studio

    base = {"session_id": "s1", "task_id": "t1", "turn_id": "turn1", "platform": "cli"}
    trace_studio.observe_lifecycle("pre_llm_call", **base, user_message="diagnostique o servidor")
    trace_studio.observe_lifecycle(
        "pre_api_request", **base, api_request_id="api1", model="m1", provider="p1",
        user_message="diagnostique o servidor",
    )
    trace_studio.observe_lifecycle(
        "post_api_request", **base, api_request_id="api1", api_duration=0.25,
        model="m1", provider="p1", usage={"input_tokens": 10, "output_tokens": 5},
    )
    trace_studio.observe_lifecycle(
        "pre_tool_call", **base, api_request_id="api1", tool_call_id="tool1", tool_name="terminal",
    )
    trace_studio.observe_lifecycle(
        "post_tool_call", **base, api_request_id="api1", tool_call_id="tool1",
        tool_name="terminal", duration_ms=12, status="ok", result={"output": "ok"},
    )
    trace_studio.observe_lifecycle(
        "post_llm_call", **base, assistant_response="Servidor verificado.", model="m1",
    )
    trace_studio.observe_lifecycle("on_session_end", **base, completed=True, model="m1")

    rows = trace_studio.list_runs()
    assert len(rows) == 1
    run = trace_studio.get_run(rows[0]["id"])
    assert run["status"] == "completed"
    assert run["model_calls"] == 1
    assert run["tool_calls"] == 1
    assert run["input_tokens"] == 10
    assert [event["event_type"] for event in run["events"]].count("post_tool_call") == 1

    from athena_cli.result_hub import list_items

    review = list_items()
    assert review[0]["source_id"] == run["id"]
    assert review[0]["status"] == "ready"


def test_result_hub_versions_artifacts(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / ".athena"))
    _reset_db()
    from athena_cli import result_hub

    source = tmp_path / "report.txt"
    source.write_text("v1", encoding="utf-8")
    item = result_hub.create_item(
        source_type="test", source_id="one", title="Report", artifacts=[source]
    )
    source.write_text("v2", encoding="utf-8")
    second = result_hub.add_artifact(item["id"], source)
    detail = result_hub.get_item(item["id"])
    assert second["version"] == 2
    assert {artifact["version"] for artifact in detail["artifacts"]} == {1, 2}
    assert result_hub.update_status(item["id"], "approved")["status"] == "approved"


def test_flows_pause_resume_retry_and_fork(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / ".athena"))
    _reset_db()
    from athena_cli import flows

    definition = {
        "name": "durable-test",
        "steps": [
            {"id": "prepare", "type": "value", "value": "ready"},
            {"id": "approve", "type": "wait", "needs": ["prepare"]},
            {"id": "finish", "type": "value", "needs": ["approve"], "value": "{{steps.approve.output.value}}"},
        ],
    }
    flows.install(definition)
    run = flows.start("durable-test", {"topic": "x"})
    waiting = flows.run(run["id"])
    assert waiting["status"] == "waiting"
    completed = flows.resume(run["id"], value="approved")
    assert completed["status"] == "completed"
    assert completed["output"]["finish"]["value"] == "approved"

    forked = flows.fork(run["id"], from_step="finish")
    assert forked["parent_run_id"] == run["id"]
    rerun = flows.run(forked["id"])
    assert rerun["status"] == "completed"


def test_router_and_canary_learn_from_outcomes(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / ".athena"))
    _reset_db()
    from athena_cli import adaptive_router, experiments

    for _ in range(5):
        adaptive_router.record_observation(
            task_kind="coding", model="strong", success=True, quality=1,
            latency_seconds=2, cost_usd=0.01, tool_success=1,
        )
        adaptive_router.record_observation(
            task_kind="coding", model="weak", success=False, quality=0,
            latency_seconds=1, cost_usd=0.001, tool_success=0,
        )
    decision = adaptive_router.recommend(
        "corrija o bug no código", current_model="weak",
        available=[{"model": "weak"}, {"model": "strong"}],
    )
    assert decision["model"] == "strong"
    experiment = experiments.create(
        "router-canary", kind="model-routing", baseline="weak", candidate="strong",
        traffic_percent=10, min_samples=2,
    )
    experiments.set_status(experiment["id"], "running")
    experiments.record(experiment["id"], "baseline", 0)
    experiments.record(experiment["id"], "baseline", 0)
    experiments.record(experiment["id"], "candidate", 1)
    result = experiments.record(experiment["id"], "candidate", 1)
    assert result["decision"] == "promote"
    assert result["status"] == "promoted"


def test_work_packages_install_flows(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / ".athena"))
    _reset_db()
    from athena_cli import flows, work_packages

    catalog = work_packages.list_packages()
    assert len(catalog["available"]) >= 6
    receipt = work_packages.install("research")
    assert receipt["name"] == "research"
    assert receipt["flows"]
    assert receipt["skills"]
    assert receipt["evals"]
    assert (tmp_path / ".athena" / "skills" / "deep-research" / "SKILL.md").is_file()
    assert any(item["name"] == "pesquisa-profunda" for item in flows.status()["definitions"])


def test_distributed_worker_claims_by_capability_and_completes(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / ".athena"))
    _reset_db()
    from athena_cli import distributed_workers as workers

    workers.register_node("cpu", name="CPU", capabilities=["command"])
    workers.register_node("gpu", name="GPU", labels=["gpu"], capabilities=["command"])
    job = workers.submit(
        "command", {"command": [sys.executable, "-c", "print('done')"]},
        requirements=["gpu"],
    )
    assert workers.claim("cpu") is None
    claimed = workers.claim("gpu")
    assert claimed and claimed["id"] == job["id"]
    completed = workers.complete("gpu", job["id"], result={"stdout": "done"})
    assert completed["status"] == "completed"


def test_evals_trajectory_checks_use_trace_data():
    from athena_cli.eval_suite import _check

    response = {
        "latency_seconds": 1.2,
        "trace": {
            "status": "completed", "tool_calls": 1, "model": "m1",
            "estimated_cost_usd": 0.01,
            "events": [{"event_type": "post_tool_call", "payload": {"tool_name": "terminal"}}],
        },
    }
    assert _check("ok", {"type": "tool_called", "value": "terminal"}, response)[0]
    assert _check("ok", {"type": "max_tool_calls", "value": 1}, response)[0]
    assert _check("ok", {"type": "max_cost_usd", "value": 0.02}, response)[0]
    assert _check("ok", {"type": "trace_status", "value": "completed"}, response)[0]


def test_trace_prune_previews_before_deleting(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / ".athena"))
    _reset_db()
    from athena_cli import trace_studio
    from athena_cli.intelligence_db import connection

    base = {"session_id": "old", "task_id": "turn", "platform": "cli"}
    trace_studio.observe_lifecycle("pre_llm_call", **base)
    trace_studio.observe_lifecycle("on_session_end", **base, completed=True)
    with connection(write=True) as conn:
        conn.execute("UPDATE trace_runs SET started_at=?,ended_at=?", (time.time() - 90 * 86400,) * 2)
    assert trace_studio.prune(max_age_days=30)["would_remove"] == 1
    assert len(trace_studio.list_runs()) == 1
    assert trace_studio.prune(max_age_days=30, execute=True)["removed"] == 1
    assert trace_studio.list_runs() == []


def test_gateway_adaptive_routing_only_changes_new_session(monkeypatch):
    from athena_cli import adaptive_router
    from gateway import session_context
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner._agent_cache = {}
    runner._agent_cache_lock = threading.RLock()
    runner._session_db = None
    runner._service_tier = None
    monkeypatch.setattr(
        session_context, "get_session_env",
        lambda key, default="": {"ATHENA_SESSION_KEY": "telegram:test", "ATHENA_SESSION_ID": "s1"}.get(key, default),
    )
    monkeypatch.setattr(
        adaptive_router, "recommend",
        lambda *args, **kwargs: {"model": "better", "provider": "same", "reason": "test"},
    )
    runtime = {"provider": "same", "requested_provider": "same", "args": []}
    route = runner._resolve_turn_agent_config("corrija o código", "base", runtime)
    assert route["model"] == "better"

    runner._agent_cache["telegram:test"] = (object(), "signature")
    route = runner._resolve_turn_agent_config("outra mensagem", "base", runtime)
    assert route["model"] == "base"
    assert "routing_decision" not in route

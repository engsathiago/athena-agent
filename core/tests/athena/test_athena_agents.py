"""Athena agent isolation, deterministic bindings and quiet heartbeat tests."""

from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path


def _home(monkeypatch, tmp_path: Path) -> Path:
    home = tmp_path / "athena"
    monkeypatch.setenv("ATHENA_HOME", str(home))
    monkeypatch.setenv("ATHENA_HOME", str(home))
    monkeypatch.setenv("ATHENA_RUNTIME", "1")
    from athena.bootstrap import initialize_home

    initialize_home(home)
    return home


def test_default_agent_has_isolated_workspace_and_manifest(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    from athena.agents import list_agents

    agents = list_agents()
    assert agents[0].id == "default"
    assert agents[0].is_default is True
    assert (home / "workspace").is_dir()
    assert (home / "memories").is_dir()
    assert (home / "security.yaml").is_file()
    assert (home / "HEARTBEAT.md").is_file()


def test_create_agent_personalizes_profile_boundary(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    profile = home / "profiles" / "coder"

    import athena_cli.profiles as profiles

    def fake_create(name, **kwargs):
        assert name == "coder"
        assert kwargs["clone_config"] is True
        for directory in ("workspace", "memories", "skills", "cron", "logs"):
            (profile / directory).mkdir(parents=True, exist_ok=True)
        return profile

    monkeypatch.setattr(profiles, "create_profile", fake_create)
    monkeypatch.setattr(profiles, "normalize_profile_name", lambda value: value.lower())

    from athena.agents import create_agent

    agent = create_agent("Coder", description="Build and review code")
    assert agent.id == "coder"
    assert "Agent ID: `coder`" in (profile / "SOUL.md").read_text(encoding="utf-8")
    manifest = json.loads((profile / "athena-agent.json").read_text(encoding="utf-8"))
    assert manifest["description"] == "Build and review code"
    assert (profile / "HEARTBEAT.md").exists()


def test_peer_binding_routes_user_to_agent_deterministically(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    profile = home / "profiles" / "coder"
    profile.mkdir(parents=True)
    (profile / "athena-agent.json").write_text(
        json.dumps({"id": "coder", "description": "Code"}), encoding="utf-8"
    )

    from athena.bindings import add_binding, routing_entries

    import athena

    route_path = Path(athena.__file__).resolve().parents[1] / "gateway" / "profile_routing.py"
    spec = importlib.util.spec_from_file_location("athena_test_profile_routing", route_path)
    assert spec and spec.loader
    routing = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = routing
    spec.loader.exec_module(routing)

    binding = add_binding("coder", "discord", user_id="u-42", chat_type="dm")
    routes = routing.parse_profile_routes(routing_entries())
    matched = routing.match_profile_route(
        routes,
        platform="discord",
        chat_id="dm-1",
        user_id="u-42",
        chat_type="dm",
    )
    missed = routing.match_profile_route(
        routes,
        platform="discord",
        chat_id="dm-1",
        user_id="someone-else",
        chat_type="dm",
    )
    assert binding["agent"] == "coder"
    assert matched is not None and matched.profile == "coder"
    assert missed is None


def test_binding_rejects_ambiguous_duplicate(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    (home / "profiles" / "coder").mkdir(parents=True)
    from athena.bindings import add_binding

    add_binding("coder", "telegram", chat_id="123")
    try:
        add_binding("default", "telegram", chat_id="123")
    except ValueError as exc:
        assert "conflicts" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("duplicate binding was accepted")


def test_heartbeat_is_profile_scoped_and_quiet(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    import cron.jobs as jobs

    captured = {}

    monkeypatch.setattr(jobs, "list_jobs", lambda include_disabled=False: [])
    monkeypatch.setattr(jobs, "update_job", lambda *args, **kwargs: None)

    def fake_create_job(**kwargs):
        captured.update(kwargs)
        return {"id": "heartbeat-job", "name": kwargs["name"]}

    monkeypatch.setattr(jobs, "create_job", fake_create_job)

    from athena.heartbeat import enable_heartbeat, heartbeat_status

    record = enable_heartbeat("default", schedule="every 45m", deliver="local")
    assert record["job_id"] == "heartbeat-job"
    assert captured["workdir"] == str(home / "workspace")
    assert "[SILENT]" in captured["prompt"]
    assert heartbeat_status("default")["schedule"] == "every 45m"

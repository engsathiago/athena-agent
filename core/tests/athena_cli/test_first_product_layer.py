from __future__ import annotations

import json
import subprocess


def _reset_intelligence_db() -> None:
    from athena_cli.intelligence_db import reset_schema_cache_for_tests

    reset_schema_cache_for_tests()


def test_studio_creates_versions_and_publishes(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / ".athena"))
    _reset_intelligence_db()
    from athena_cli import artifact_studio, result_hub

    artifact = artifact_studio.create_artifact(kind="document", title="Plano")
    assert artifact["preview_kind"] == "markdown"
    assert artifact["version"] == 1

    saved = artifact_studio.save_content(
        artifact["id"], content="# Plano\n\nVersão aprovada.\n"
    )
    assert saved["version"] == 2
    assert saved["content"].endswith("Versão aprovada.\n")
    assert saved["versions"]

    published = artifact_studio.publish(artifact["id"])
    assert published["artifact"]["published_result_id"]
    result = result_hub.get_item(published["result"]["id"])
    assert result["artifacts"][0]["name"] == "documento.md"


def test_mission_control_creates_instructs_pauses_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / ".athena"))
    monkeypatch.setenv("ATHENA_KANBAN_BOARD", "default")
    _reset_intelligence_db()
    from athena_cli import mission_control

    task = mission_control.create_task(
        board="default", title="Preparar lançamento", body="Gerar os materiais"
    )
    assert task["status"] == "ready"
    instructed = mission_control.send_instruction(
        task["id"], board="default", message="Priorize a documentação"
    )
    assert instructed["task"]["comments"][-1]["body"] == "Priorize a documentação"

    paused = mission_control.act(task["id"], board="default", action="pause")
    assert paused["task"]["status"] == "blocked"
    resumed = mission_control.act(task["id"], board="default", action="resume")
    assert resumed["task"]["status"] == "ready"
    overview = mission_control.overview(board="default")
    assert any(row["id"] == task["id"] for row in overview["tasks"])


def test_environment_manager_tracks_lifecycle_without_real_docker(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / ".athena"))
    from athena_cli import sandbox_manager

    state = {"running": True}

    def fake_run(args, timeout=90):
        if args[0] == "run":
            return subprocess.CompletedProcess(args, 0, stdout="container-123\n", stderr="")
        if args[0] == "inspect":
            payload = {"Running": state["running"], "Paused": False, "Dead": False, "ExitCode": 0, "Error": ""}
            return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")
        if args[0] in {"start", "restart"}:
            state["running"] = True
        elif args[0] in {"stop", "rm"}:
            state["running"] = False
        return subprocess.CompletedProcess(args, 0, stdout="ok\n", stderr="")

    monkeypatch.setattr(sandbox_manager, "_run", fake_run)
    monkeypatch.setattr(
        sandbox_manager,
        "capabilities",
        lambda: {"drivers": [{"id": "docker", "available": True}], "default_image": "image"},
    )
    environment = sandbox_manager.create_environment(
        name="Teste", image="image", ttl_minutes=10, persistent=True
    )
    assert environment["status"] == "running"
    assert sandbox_manager.list_environments()["counts"]["running"] == 1
    assert sandbox_manager.control(environment["id"], "stop")["status"] == "stopped"
    assert sandbox_manager.snapshot(environment["id"])["snapshot"]["image"].startswith("athena-snapshot:")
    assert sandbox_manager.delete_environment(environment["id"])["ok"]
    assert sandbox_manager.list_environments()["environments"] == []

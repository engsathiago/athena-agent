from __future__ import annotations

import json
import sqlite3
import time
import zipfile
from pathlib import Path


def test_eval_suite_runs_and_compares_with_injected_runner(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / "home"))
    from athena_cli import eval_suite

    suite = eval_suite.init_suite("small", count=2)

    def runner(prompt: str, timeout: float):
        del timeout
        output = "42" if "17 + 25" in prompt else "72"
        return {"output": output, "stderr": "", "returncode": 0, "latency_seconds": 0.01}

    report = eval_suite.run_suite(suite["path"], runner=runner)
    assert report["score"] == 1.0
    assert Path(report["report_path"]).is_file()
    comparison = eval_suite.compare_reports(report["report_path"], report["report_path"])
    assert comparison["decision"] == "accept"

    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps({"score": 1.0}), encoding="utf-8")
    candidate.write_text(json.dumps({"score": 0.99}), encoding="utf-8")
    assert eval_suite.compare_reports(baseline, candidate, max_regression=0.02)["accepted"] is True


def test_memory_maintenance_archives_only_safe_origins(tmp_path):
    from plugins.memory.athena.store import AthenaMemoryStore

    store = AthenaMemoryStore(str(tmp_path / "memory.db"))
    owner = store.remember("Preferência importante do dono", trust_origin="owner", confidence=0.1)
    agent = store.remember("Hipótese antiga do agente", trust_origin="agent", confidence=0.1)
    old = time.time() - 365 * 86400
    store._conn.execute("UPDATE memories SET updated_at = ?", (old,))
    store._conn.commit()

    result = store.maintain(dry_run=False, stale_after_days=180, low_confidence=0.35)
    assert result["archived"] == 1
    assert store.get(owner["id"])["status"] == "active"
    assert store.get(agent["id"])["status"] == "archived"
    store.close()


def test_backup_verification_checks_sqlite_and_archive_safety(tmp_path):
    from athena_cli.backup import verify_backup_archive

    database = tmp_path / "state.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    archive = tmp_path / "athena-backup-test.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("config.yaml", "model: {}\n")
        zf.write(database, "state.db")
    result = verify_backup_archive(archive)
    assert result["valid"] is True
    assert result["sqlite"][0]["valid"] is True

    unsafe = tmp_path / "athena-backup-unsafe.zip"
    with zipfile.ZipFile(unsafe, "w") as zf:
        zf.writestr("config.yaml", "model: {}\n")
        zf.writestr("../outside.txt", "no")
    assert verify_backup_archive(unsafe)["valid"] is False


def test_skill_evolution_requires_evaluation_and_rolls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / "home"))
    from athena_cli import evolution

    source = tmp_path / "candidate"
    source.mkdir()
    (source / "SKILL.md").write_text("# New skill\n", encoding="utf-8")
    live = tmp_path / "home" / "skills" / "writer"
    live.mkdir(parents=True)
    (live / "SKILL.md").write_text("# Old skill\n", encoding="utf-8")
    proposal = evolution.propose(source, name="writer", reason="better result")

    try:
        evolution.activate(proposal["id"])
        assert False, "activation should require an accepted evaluation"
    except ValueError:
        pass

    report = tmp_path / "report.json"
    report.write_text(json.dumps({"score": 1.0, "failed": 0}), encoding="utf-8")
    evolution.evaluate(proposal["id"], report)
    evolution.activate(proposal["id"])
    assert (live / "SKILL.md").read_text(encoding="utf-8") == "# New skill\n"
    evolution.rollback(proposal["id"])
    assert (live / "SKILL.md").read_text(encoding="utf-8") == "# Old skill\n"


def test_offline_configuration_uses_local_ollama_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / "home"))
    from athena_cli import offline

    monkeypatch.setattr(
        offline,
        "probe_ollama",
        lambda *args, **kwargs: {
            "service_reachable": True,
            "models": ["qwen3:8b"],
            "base_url": "http://127.0.0.1:11434",
        },
    )
    result = offline.configure_ollama("qwen3:8b")
    text = Path(result["config"]).read_text(encoding="utf-8")
    assert "qwen3:8b" in text
    assert "http://127.0.0.1:11434/v1" in text
    assert "provider: custom" in text


def test_offline_bundle_contains_installer_source_and_manifest(tmp_path):
    from athena_cli import offline

    source = tmp_path / "source"
    (source / "core").mkdir(parents=True)
    (source / "core" / "pyproject.toml").write_text("[project]\nname='athena-test'\nversion='0.0.0'\n", encoding="utf-8")
    (source / "install-offline.sh").write_text("#!/usr/bin/env sh\n", encoding="utf-8")
    result = offline.prepare_bundle(tmp_path / "bundle", source_root=source)
    assert Path(result["manifest"]).is_file()
    assert (tmp_path / "bundle" / "athena-app" / "core" / "pyproject.toml").is_file()
    assert (tmp_path / "bundle" / "install-offline.sh").is_file()

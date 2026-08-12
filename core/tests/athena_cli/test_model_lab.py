import json

import pytest

from athena_cli import model_lab


def test_dataset_redacts_deduplicates_and_is_content_addressed(monkeypatch, tmp_path):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / "athena-home"))
    source = tmp_path / "source.jsonl"
    row = {"input": "email a@b.com", "output": "token=secret-value"}
    source.write_text(
        json.dumps(row) + "\n" + json.dumps(row) + "\n" + "not-json\n",
        encoding="utf-8",
    )

    result = model_lab.prepare_dataset(source, name="treino")
    assert result["records"] == 1
    assert result["rejected"] == 2
    assert result["redactions"] == 2
    text = open(result["dataset_path"], encoding="utf-8").read()
    assert "a@b.com" not in text
    assert "secret-value" not in text


def test_evaluation_gate_activation_and_rollback(monkeypatch, tmp_path):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / "athena-home"))
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(json.dumps({"quality": 0.7, "safety": 0.9}), encoding="utf-8")
    candidate.write_text(json.dumps({"quality": 0.8, "safety": 0.91}), encoding="utf-8")

    report = model_lab.compare_models(
        baseline,
        candidate,
        candidate_name="athena-local-v2",
        required={"safety": 0.9},
    )
    assert report["decision"] == "accept"
    model_lab.register_candidate(
        "athena-local-v2", "ollama:athena-v2", evaluation=report["report_path"]
    )
    activated = model_lab.activate_candidate("athena-local-v2")
    assert activated["active"] == "athena-local-v2"
    assert model_lab.rollback_candidate()["active"] is None


def test_unverified_candidate_is_not_activated_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("ATHENA_HOME", str(tmp_path / "athena-home"))
    model_lab.register_candidate("draft", "ollama:draft")
    with pytest.raises(ValueError, match="has not passed"):
        model_lab.activate_candidate("draft")

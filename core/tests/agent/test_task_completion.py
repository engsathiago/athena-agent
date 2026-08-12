from agent.task_completion import (
    artifact_evidence,
    assess_completion_evidence,
    normalize_completion_evidence,
)


def test_normalize_completion_evidence_accepts_command_and_exit_code():
    evidence = normalize_completion_evidence(
        [{"kind": "test", "command": "pytest -q", "exit_code": 0}]
    )
    assert evidence[0]["status"] == "passed"
    assert assess_completion_evidence(evidence)["verified"] is True


def test_plain_prose_is_a_claim_not_proof():
    evidence = normalize_completion_evidence("I finished everything")
    assessment = assess_completion_evidence(evidence)
    assert assessment["status"] == "claimed"
    assert assessment["verified"] is False


def test_existing_artifact_counts_as_verified(tmp_path):
    deliverable = tmp_path / "report.pdf"
    deliverable.write_bytes(b"pdf")
    assessment = assess_completion_evidence(artifact_evidence([str(deliverable)]))
    assert assessment["status"] == "verified"


def test_failed_evidence_wins_over_passed_evidence():
    evidence = normalize_completion_evidence(
        [
            {"kind": "test", "status": "passed"},
            {"kind": "lint", "status": "failed"},
        ]
    )
    assert assess_completion_evidence(evidence)["status"] == "failed"

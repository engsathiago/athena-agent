"""Repeatable, local evaluation suites for Athena.

Suites are JSONL files.  Every run invokes the real Athena one-shot command,
checks the plain-text answer, and writes an immutable JSON report that can be
compared before a model, prompt, or skill change is accepted.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from athena_constants import get_athena_home


_STARTER_CASES: list[dict[str, Any]] = [
    {"id": "math-01", "prompt": "Responda apenas com o resultado de 17 + 25.", "checks": [{"type": "contains", "value": "42"}], "tags": ["raciocinio"]},
    {"id": "math-02", "prompt": "Responda apenas com o resultado de 9 vezes 8.", "checks": [{"type": "contains", "value": "72"}], "tags": ["raciocinio"]},
    {"id": "math-03", "prompt": "Qual é a metade de 144? Responda de forma curta.", "checks": [{"type": "contains", "value": "72"}], "tags": ["raciocinio"]},
    {"id": "logic-01", "prompt": "Se todos os lírios são flores e esta planta é um lírio, complete: esta planta é uma ___.", "checks": [{"type": "contains", "value": "flor"}], "tags": ["raciocinio"]},
    {"id": "logic-02", "prompt": "Ana chegou antes de Bia, e Bia antes de Carla. Quem chegou primeiro?", "checks": [{"type": "contains", "value": "Ana"}], "tags": ["raciocinio"]},
    {"id": "pt-01", "prompt": "Corrija a frase e responda apenas com a versão correta: nós vai amanhã.", "checks": [{"type": "contains", "value": "Nós vamos amanhã"}], "tags": ["portugues"]},
    {"id": "pt-02", "prompt": "Dê um sinônimo de rápido em uma única palavra.", "checks": [{"type": "max_words", "value": 2}], "tags": ["portugues"]},
    {"id": "pt-03", "prompt": "Resuma em no máximo 8 palavras: A chuva forte atrasou o trânsito durante toda a manhã.", "checks": [{"type": "max_words", "value": 8}], "tags": ["resumo"]},
    {"id": "class-01", "prompt": "Classifique como positivo, negativo ou neutro: 'O atendimento foi excelente'.", "checks": [{"type": "contains", "value": "positivo"}], "tags": ["classificacao"]},
    {"id": "class-02", "prompt": "Classifique como positivo, negativo ou neutro: 'O produto chegou quebrado'.", "checks": [{"type": "contains", "value": "negativo"}], "tags": ["classificacao"]},
    {"id": "class-03", "prompt": "Classifique como positivo, negativo ou neutro: 'A reunião será às 14h'.", "checks": [{"type": "contains", "value": "neutro"}], "tags": ["classificacao"]},
    {"id": "json-01", "prompt": "Responda somente em JSON válido com a chave status e o valor ok.", "checks": [{"type": "json"}, {"type": "contains", "value": "status"}], "tags": ["estrutura"]},
    {"id": "json-02", "prompt": "Responda somente em JSON válido: uma lista com os números 1, 2 e 3.", "checks": [{"type": "json"}], "tags": ["estrutura"]},
    {"id": "format-01", "prompt": "Escreva exatamente três itens, um por linha, sobre hábitos de estudo.", "checks": [{"type": "regex", "value": "(?m)^.+\\n.+\\n.+$"}], "tags": ["estrutura"]},
    {"id": "code-01", "prompt": "Em Python, qual função embutida retorna o tamanho de uma lista? Responda só com o nome.", "checks": [{"type": "contains", "value": "len"}, {"type": "max_words", "value": 3}], "tags": ["codigo"]},
    {"id": "code-02", "prompt": "Qual palavra-chave Python define uma função? Responda só com ela.", "checks": [{"type": "contains", "value": "def"}, {"type": "max_words", "value": 3}], "tags": ["codigo"]},
    {"id": "code-03", "prompt": "Qual comando Git mostra o estado atual dos arquivos? Responda de forma curta.", "checks": [{"type": "contains", "value": "git status"}], "tags": ["codigo"]},
    {"id": "code-04", "prompt": "Em SQL, qual cláusula filtra linhas? Responda só com a palavra-chave.", "checks": [{"type": "contains", "value": "WHERE"}], "tags": ["codigo"]},
    {"id": "fact-01", "prompt": "Qual planeta é conhecido como planeta vermelho?", "checks": [{"type": "contains", "value": "Marte"}], "tags": ["conhecimento"]},
    {"id": "fact-02", "prompt": "Qual é a capital do Brasil?", "checks": [{"type": "contains", "value": "Brasília"}], "tags": ["conhecimento"]},
    {"id": "fact-03", "prompt": "Quantos dias há em uma semana?", "checks": [{"type": "contains", "value": "7"}], "tags": ["conhecimento"]},
    {"id": "instruction-01", "prompt": "Responda apenas SIM, em letras maiúsculas.", "checks": [{"type": "regex", "value": "^\\s*SIM[.!]?\\s*$"}], "tags": ["instrucao"]},
    {"id": "instruction-02", "prompt": "Responda apenas com a palavra Athena.", "checks": [{"type": "regex", "value": "^\\s*Athena[.!]?\\s*$"}], "tags": ["instrucao"]},
    {"id": "instruction-03", "prompt": "Explique o que é cache em no máximo 15 palavras.", "checks": [{"type": "max_words", "value": 15}], "tags": ["instrucao"]},
    {"id": "extract-01", "prompt": "Extraia apenas o e-mail: Contato: Maria <maria@example.com> para suporte.", "checks": [{"type": "contains", "value": "maria@example.com"}], "tags": ["extracao"]},
    {"id": "extract-02", "prompt": "Extraia apenas a data: O evento acontece em 21/09/2026 às 10h.", "checks": [{"type": "contains", "value": "21/09/2026"}], "tags": ["extracao"]},
    {"id": "transform-01", "prompt": "Converta para maiúsculas e responda apenas o resultado: athena agent.", "checks": [{"type": "contains", "value": "ATHENA AGENT"}], "tags": ["transformacao"]},
    {"id": "transform-02", "prompt": "Ordene alfabeticamente e responda em uma linha: zebra, casa, abelha.", "checks": [{"type": "regex", "value": "(?i)abelha.*casa.*zebra"}], "tags": ["transformacao"]},
    {"id": "planning-01", "prompt": "Dê exatamente dois passos curtos para fazer backup antes de uma atualização.", "checks": [{"type": "max_words", "value": 35}], "tags": ["planejamento"]},
    {"id": "clarity-01", "prompt": "Explique RAM para uma pessoa leiga em no máximo 20 palavras.", "checks": [{"type": "max_words", "value": 20}], "tags": ["clareza"]},
]


def _root() -> Path:
    return get_athena_home() / "evals"


def init_suite(name: str = "starter", *, count: int = 30, overwrite: bool = False) -> dict[str, Any]:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", name).strip("-.") or "starter"
    count = max(1, min(int(count), len(_STARTER_CASES)))
    path = _root() / "suites" / f"{safe}.jsonl"
    if path.exists() and not overwrite:
        raise FileExistsError(f"suite already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in _STARTER_CASES[:count]), encoding="utf-8")
    return {"suite": safe, "path": str(path), "cases": count}


def resolve_suite(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_file():
        return path.resolve()
    candidate = _root() / "suites" / f"{value}.jsonl"
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"evaluation suite not found: {value}")


def _load_suite(path: Path) -> list[dict[str, Any]]:
    cases = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        if not case.get("id") or not case.get("prompt"):
            raise ValueError(f"invalid case at line {line_no}")
        cases.append(case)
    if not cases:
        raise ValueError("evaluation suite is empty")
    return cases


def _athena_command() -> list[str]:
    executable = shutil.which("athena")
    return [executable] if executable else [sys.executable, "-m", "athena_cli.main"]


def _default_runner(prompt: str, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    run_key = f"eval-{uuid.uuid4().hex}"
    env = os.environ.copy()
    env["ATHENA_EVAL_RUN_KEY"] = run_key
    proc = subprocess.run(
        [*_athena_command(), "-z", prompt],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=env,
    )
    response = {
        "output": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "returncode": proc.returncode,
        "latency_seconds": round(time.monotonic() - started, 4),
    }
    try:
        from athena_cli.trace_studio import find_by_run_key
        response["trace"] = find_by_run_key(run_key)
    except Exception:
        response["trace"] = None
    return response


def _check(output: str, check: dict[str, Any], response: dict[str, Any] | None = None) -> tuple[bool, str]:
    kind = str(check.get("type") or "").lower()
    value = check.get("value")
    if kind == "contains":
        ok = str(value).casefold() in output.casefold()
    elif kind == "not_contains":
        ok = str(value).casefold() not in output.casefold()
    elif kind == "regex":
        ok = re.search(str(value), output) is not None
    elif kind == "json":
        try:
            json.loads(output)
            ok = True
        except json.JSONDecodeError:
            ok = False
    elif kind == "max_words":
        ok = len(output.split()) <= int(value)
    elif kind in {"tool_called", "tool_not_called"}:
        trace = (response or {}).get("trace") or {}
        called = {
            str(event.get("payload", {}).get("tool_name") or "")
            for event in trace.get("events") or []
            if event.get("event_type") == "post_tool_call"
        }
        present = str(value) in called
        ok = present if kind == "tool_called" else not present
    elif kind == "max_tool_calls":
        trace = (response or {}).get("trace") or {}
        ok = int(trace.get("tool_calls") or 0) <= int(value)
    elif kind == "min_tool_calls":
        trace = (response or {}).get("trace") or {}
        ok = int(trace.get("tool_calls") or 0) >= int(value)
    elif kind == "model_is":
        trace = (response or {}).get("trace") or {}
        ok = str(trace.get("model") or "") == str(value)
    elif kind == "provider_is":
        trace = (response or {}).get("trace") or {}
        ok = str(trace.get("provider") or "") == str(value)
    elif kind == "max_latency_seconds":
        ok = float((response or {}).get("latency_seconds") or 0) <= float(value)
    elif kind == "max_cost_usd":
        trace = (response or {}).get("trace") or {}
        ok = float(trace.get("estimated_cost_usd") or 0) <= float(value)
    elif kind == "trace_status":
        trace = (response or {}).get("trace") or {}
        ok = str(trace.get("status") or "") == str(value)
    elif kind == "artifact_exists":
        ok = Path(str(value)).expanduser().is_file()
    else:
        return False, f"unknown check: {kind}"
    return ok, f"{kind}={value!r}"


def run_suite(
    suite: str | Path,
    *,
    repetitions: int = 1,
    timeout: float = 120.0,
    runner: Callable[[str, float], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    path = resolve_suite(suite)
    cases = _load_suite(path)
    repetitions = max(1, min(int(repetitions), 10))
    execute = runner or _default_runner
    results: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        for case in cases:
            try:
                response = execute(str(case["prompt"]), float(timeout))
                output = str(response.get("output") or "")
                check_results = []
                for check in case.get("checks") or []:
                    ok, label = _check(output, check, response)
                    check_results.append({"passed": ok, "check": label})
                passed = int(response.get("returncode", 1)) == 0 and bool(check_results) and all(item["passed"] for item in check_results)
                error = str(response.get("stderr") or "") if response.get("returncode") else ""
            except Exception as exc:  # one bad case must not erase the run
                output, check_results, passed, error = "", [], False, str(exc)
                response = {"latency_seconds": 0.0, "returncode": 1}
            results.append({
                "id": case["id"], "repetition": repetition, "passed": passed,
                "checks": check_results, "output": output[:12000], "error": error[:4000],
                "latency_seconds": float(response.get("latency_seconds") or 0.0),
                "trace_id": ((response.get("trace") or {}).get("id")),
                "model": ((response.get("trace") or {}).get("model")),
                "provider": ((response.get("trace") or {}).get("provider")),
                "tool_calls": int((response.get("trace") or {}).get("tool_calls") or 0),
                "model_calls": int((response.get("trace") or {}).get("model_calls") or 0),
                "estimated_cost_usd": float((response.get("trace") or {}).get("estimated_cost_usd") or 0),
                "tags": case.get("tags") or [],
            })
    passed_count = sum(1 for item in results if item["passed"])
    total = len(results)
    report = {
        "schema_version": 1,
        "suite": path.stem,
        "suite_path": str(path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repetitions": repetitions,
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "score": round(passed_count / total, 6),
        "latency_seconds": round(sum(item["latency_seconds"] for item in results), 4),
        "estimated_cost_usd": round(sum(item["estimated_cost_usd"] for item in results), 8),
        "tool_calls": sum(item["tool_calls"] for item in results),
        "model_calls": sum(item["model_calls"] for item in results),
        "results": results,
    }
    runs = _root() / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report_path = runs / f"{path.stem}-{stamp}.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def import_traces(
    name: str = "real-trajectories", *, limit: int = 50, include_failed: bool = True,
) -> dict[str, Any]:
    """Turn recent real, locally captured runs into an editable regression suite."""
    from athena_cli.trace_studio import get_run, list_runs

    cases = []
    for row in list_runs(limit=limit):
        if not include_failed and row.get("status") != "completed":
            continue
        trace = get_run(row["id"])
        prompt = str((trace.get("metadata") or {}).get("prompt") or "").strip()
        if not prompt:
            continue
        tools = []
        for event in trace.get("events") or []:
            if event.get("event_type") == "post_tool_call":
                tool = str((event.get("payload") or {}).get("tool_name") or "")
                if tool and tool not in tools:
                    tools.append(tool)
        checks: list[dict[str, Any]] = [{"type": "trace_status", "value": "completed"}]
        checks.extend({"type": "tool_called", "value": tool} for tool in tools)
        cases.append({
            "id": f"trace-{row['id']}", "prompt": prompt, "checks": checks,
            "tags": ["real", "trajectory"], "source_trace": row["id"],
        })
    if not cases:
        raise ValueError("no trace with a reusable prompt was found")
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", name).strip("-.") or "real-trajectories"
    path = _root() / "suites" / f"{safe}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8")
    return {"suite": safe, "path": str(path), "cases": len(cases)}


def ci_gate(
    suite: str | Path, *, min_score: float = 0.9, max_latency_seconds: float | None = None,
    baseline: str | Path | None = None, max_regression: float = 0.02,
    repetitions: int = 1, timeout: float = 120.0,
) -> dict[str, Any]:
    report = run_suite(suite, repetitions=repetitions, timeout=timeout)
    reasons = []
    if float(report["score"]) < float(min_score):
        reasons.append(f"score {report['score']:.3f} below {min_score:.3f}")
    if max_latency_seconds is not None and float(report["latency_seconds"]) > float(max_latency_seconds):
        reasons.append(f"latency {report['latency_seconds']:.3f}s above {max_latency_seconds:.3f}s")
    comparison = None
    if baseline:
        comparison = compare_reports(baseline, report["report_path"], max_regression=max_regression)
        if not comparison["accepted"]:
            reasons.append(f"regression {comparison['delta']:.3f} exceeds allowance")
    return {"accepted": not reasons, "decision": "accept" if not reasons else "reject", "reasons": reasons, "report": report, "comparison": comparison}


def compare_reports(
    baseline: str | Path,
    candidate: str | Path,
    *,
    max_regression: float = 0.02,
    min_improvement: float = 0.0,
) -> dict[str, Any]:
    base = json.loads(Path(baseline).expanduser().read_text(encoding="utf-8"))
    cand = json.loads(Path(candidate).expanduser().read_text(encoding="utf-8"))
    delta = float(cand["score"]) - float(base["score"])
    required_improvement = max(0.0, float(min_improvement))
    accepted = delta >= -abs(float(max_regression)) and (
        required_improvement == 0.0 or delta >= required_improvement
    )
    return {
        "decision": "accept" if accepted else "reject",
        "accepted": accepted,
        "baseline_score": float(base["score"]),
        "candidate_score": float(cand["score"]),
        "delta": round(delta, 6),
        "max_regression": float(max_regression),
        "min_improvement": required_improvement,
    }


def status() -> dict[str, Any]:
    suites = sorted((_root() / "suites").glob("*.jsonl")) if (_root() / "suites").exists() else []
    runs = sorted((_root() / "runs").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if (_root() / "runs").exists() else []
    latest = None
    if runs:
        try:
            data = json.loads(runs[0].read_text(encoding="utf-8"))
            latest = {key: data.get(key) for key in ("suite", "created_at", "total", "passed", "failed", "score", "report_path")}
        except (OSError, json.JSONDecodeError):
            latest = {"report_path": str(runs[0]), "invalid": True}
    return {"suites": [str(path) for path in suites], "run_count": len(runs), "latest": latest}

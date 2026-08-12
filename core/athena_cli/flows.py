"""Durable, resumable Athena workflows with step-level checkpoints."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

import yaml

from athena_cli.intelligence_db import connection


TERMINAL = {"completed", "skipped"}
_VAR = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")


def _load_definition(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        definition = source
    else:
        path = Path(source).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"flow definition not found: {path}")
        definition = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(definition, dict):
        raise ValueError("flow definition must be an object")
    name = str(definition.get("name") or "").strip()
    steps = definition.get("steps")
    if not name or not isinstance(steps, list) or not steps:
        raise ValueError("flow requires a name and at least one step")
    seen: set[str] = set()
    for step in steps:
        if not isinstance(step, dict) or not str(step.get("id") or "").strip():
            raise ValueError("every flow step requires an id")
        step_id = str(step["id"])
        if step_id in seen:
            raise ValueError(f"duplicate flow step: {step_id}")
        seen.add(step_id)
    for step in steps:
        unknown = set(step.get("needs") or []) - seen
        if unknown:
            raise ValueError(f"step {step['id']} depends on unknown steps: {sorted(unknown)}")
    return definition


def install(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    definition = _load_definition(source)
    now = time.time()
    name = str(definition["name"])
    with connection(write=True) as conn:
        previous = conn.execute("SELECT id,version FROM flow_definitions WHERE name=?", (name,)).fetchone()
        flow_id = str(previous["id"]) if previous else f"flow_{uuid.uuid4().hex[:20]}"
        version = int(previous["version"]) + 1 if previous else 1
        payload = json.dumps(definition, ensure_ascii=False)
        if previous:
            conn.execute(
                "UPDATE flow_definitions SET version=?,definition=?,updated_at=? WHERE id=?",
                (version, payload, now, flow_id),
            )
        else:
            conn.execute(
                "INSERT INTO flow_definitions(id,name,version,definition,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (flow_id, name, version, payload, now, now),
            )
    return {"id": flow_id, "name": name, "version": version, "steps": len(definition["steps"])}


def _definition(flow: str) -> tuple[str, dict[str, Any]]:
    with connection() as conn:
        row = conn.execute(
            "SELECT id,definition FROM flow_definitions WHERE id=? OR name=?", (flow, flow)
        ).fetchone()
    if row is None:
        raise FileNotFoundError(f"flow not found: {flow}")
    return str(row["id"]), json.loads(row["definition"])


def start(flow: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    flow_id, definition = _definition(flow)
    run_id = f"fr_{uuid.uuid4().hex[:20]}"
    now = time.time()
    with connection(write=True) as conn:
        conn.execute(
            "INSERT INTO flow_runs(id,flow_id,status,input,created_at,updated_at) VALUES(?,?, 'pending',?,?,?)",
            (run_id, flow_id, json.dumps(inputs or {}, ensure_ascii=False), now, now),
        )
        for step in definition["steps"]:
            conn.execute(
                "INSERT INTO flow_step_runs(run_id,step_id,status) VALUES(?,?, 'pending')",
                (run_id, str(step["id"])),
            )
    return get_run(run_id)


def _context(run: dict[str, Any]) -> dict[str, Any]:
    return {"input": run["input"], "steps": {step["step_id"]: step for step in run["steps"]}}


def _lookup(context: dict[str, Any], dotted: str) -> Any:
    current: Any = context
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return ""
        current = current[part]
    return current


def _render(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        match = _VAR.fullmatch(value)
        if match:
            return _lookup(context, match.group(1))
        return _VAR.sub(lambda m: str(_lookup(context, m.group(1))), value)
    if isinstance(value, list):
        return [_render(item, context) for item in value]
    if isinstance(value, dict):
        return {str(key): _render(item, context) for key, item in value.items()}
    return value


def _condition_met(condition: Any, context: dict[str, Any]) -> bool:
    if condition is None:
        return True
    rendered = _render(condition, context)
    if isinstance(rendered, bool):
        return rendered
    if isinstance(rendered, dict):
        actual = _lookup(context, str(rendered.get("path") or ""))
        if "equals" in rendered:
            return actual == rendered["equals"]
        if "not_equals" in rendered:
            return actual != rendered["not_equals"]
        return bool(actual)
    return str(rendered).strip().casefold() not in {"", "0", "false", "none", "no"}


def _athena_command() -> list[str]:
    executable = shutil.which("athena")
    return [executable] if executable else [sys.executable, "-m", "athena_cli.main"]


def _execute_step(step: dict[str, Any], context: dict[str, Any], run_id: str) -> dict[str, Any]:
    rendered = _render(step, context)
    kind = str(rendered.get("type") or "command")
    timeout = float(rendered.get("timeout") or 600)
    env = os.environ.copy()
    env["ATHENA_FLOW_RUN_ID"] = run_id
    if kind == "wait":
        return {"waiting": True, "message": str(rendered.get("message") or "Aguardando continuação")}
    if kind == "value":
        return {"value": rendered.get("value")}
    if kind == "athena":
        prompt = str(rendered.get("prompt") or "")
        command = [*_athena_command(), "-z", prompt]
    elif kind == "command":
        command_value = rendered.get("command")
        command = [str(item) for item in command_value] if isinstance(command_value, list) else shlex.split(str(command_value or ""))
        if not command:
            raise ValueError(f"step {step['id']} has an empty command")
    else:
        raise ValueError(f"unsupported flow step type: {kind}")
    started = time.monotonic()
    proc = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False, env=env)
    output = {
        "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(),
        "returncode": proc.returncode, "duration_seconds": round(time.monotonic() - started, 4),
    }
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"command exited with {proc.returncode}")
    if kind == "athena":
        output["response"] = proc.stdout.strip()
    return output


def run(run_id: str, *, max_parallel: int = 4, executor: Callable[[dict[str, Any], dict[str, Any], str], dict[str, Any]] | None = None) -> dict[str, Any]:
    execute = executor or _execute_step
    while True:
        current = get_run(run_id)
        if current["status"] in {"completed", "cancelled"}:
            return current
        _, definition = _definition(current["flow_id"])
        by_id = {str(step["id"]): step for step in definition["steps"]}
        state = {step["step_id"]: step["status"] for step in current["steps"]}
        if any(status == "waiting" for status in state.values()):
            _set_run_status(run_id, "waiting")
            return get_run(run_id)
        ready = [
            by_id[step_id] for step_id, status in state.items()
            if status in {"pending", "failed"}
            and all(state.get(dep) in TERMINAL for dep in by_id[step_id].get("needs") or [])
            and (status != "failed" or int(next(s for s in current["steps"] if s["step_id"] == step_id)["attempt"]) <= int(by_id[step_id].get("retries") or 0))
        ]
        if not ready:
            if all(status in TERMINAL for status in state.values()):
                output = {step["step_id"]: step["output"] for step in current["steps"]}
                _finish_run(run_id, "completed", output=output)
            elif any(status == "failed" for status in state.values()):
                _finish_run(run_id, "failed", error="one or more steps exhausted their retries")
            else:
                _finish_run(run_id, "failed", error="flow dependency deadlock")
            return get_run(run_id)
        _set_run_status(run_id, "running")
        context = _context(current)
        runnable: list[dict[str, Any]] = []
        for step in ready:
            if _condition_met(step.get("when"), context):
                runnable.append(step)
            else:
                _finish_step(run_id, str(step["id"]), "skipped", output={"reason": "condition_false"})
        if not runnable:
            continue
        results: dict[str, tuple[str, dict[str, Any] | None, str]] = {}
        with ThreadPoolExecutor(max_workers=max(1, min(int(max_parallel), len(runnable)))) as pool:
            future_map = {}
            for step in runnable:
                step_id = str(step["id"])
                _start_step(run_id, step_id, _render(step, context))
                future_map[pool.submit(execute, step, context, run_id)] = step_id
            for future in as_completed(future_map):
                step_id = future_map[future]
                try:
                    output = future.result()
                    status = "waiting" if output.get("waiting") else "completed"
                    results[step_id] = (status, output, "")
                except Exception as exc:
                    results[step_id] = ("failed", None, str(exc))
        for step_id, (status, output, error) in results.items():
            _finish_step(run_id, step_id, status, output=output or {}, error=error)


def resume(run_id: str, *, step_id: str | None = None, value: Any = None, max_parallel: int = 4) -> dict[str, Any]:
    current = get_run(run_id)
    waiting = [step for step in current["steps"] if step["status"] == "waiting"]
    if step_id:
        waiting = [step for step in waiting if step["step_id"] == step_id]
    if not waiting:
        raise ValueError("flow has no matching waiting step")
    for step in waiting:
        _finish_step(run_id, step["step_id"], "completed", output={"value": value, "resumed": True})
    return run(run_id, max_parallel=max_parallel)


def retry(run_id: str, step_id: str) -> dict[str, Any]:
    with connection(write=True) as conn:
        cursor = conn.execute(
            "UPDATE flow_step_runs SET status='pending',error='',ended_at=NULL WHERE run_id=? AND step_id=?",
            (run_id, step_id),
        )
        if cursor.rowcount != 1:
            raise FileNotFoundError(f"flow step not found: {run_id}/{step_id}")
        conn.execute("UPDATE flow_runs SET status='pending',error='',updated_at=? WHERE id=?", (time.time(), run_id))
    return run(run_id)


def fork(run_id: str, *, from_step: str) -> dict[str, Any]:
    source = get_run(run_id)
    _, definition = _definition(source["flow_id"])
    ids = [str(step["id"]) for step in definition["steps"]]
    if from_step not in ids:
        raise ValueError(f"unknown flow step: {from_step}")
    child = start(source["flow_id"], source["input"])
    cutoff = ids.index(from_step)
    source_steps = {step["step_id"]: step for step in source["steps"]}
    with connection(write=True) as conn:
        conn.execute("UPDATE flow_runs SET parent_run_id=? WHERE id=?", (run_id, child["id"]))
        for step_id in ids[:cutoff]:
            old = source_steps[step_id]
            if old["status"] in TERMINAL:
                conn.execute(
                    """UPDATE flow_step_runs SET status=?,attempt=?,started_at=?,ended_at=?,input=?,output=?,checkpoint=?
                       WHERE run_id=? AND step_id=?""",
                    (old["status"], old["attempt"], old["started_at"], old["ended_at"],
                     json.dumps(old["input"], ensure_ascii=False), json.dumps(old["output"], ensure_ascii=False),
                     json.dumps({"forked_from": run_id}, ensure_ascii=False), child["id"], step_id),
                )
    return get_run(child["id"])


def _set_run_status(run_id: str, status: str) -> None:
    with connection(write=True) as conn:
        conn.execute("UPDATE flow_runs SET status=?,updated_at=? WHERE id=?", (status, time.time(), run_id))


def _finish_run(run_id: str, status: str, *, output: dict[str, Any] | None = None, error: str = "") -> None:
    with connection(write=True) as conn:
        conn.execute(
            "UPDATE flow_runs SET status=?,output=?,error=?,updated_at=? WHERE id=?",
            (status, json.dumps(output or {}, ensure_ascii=False), error, time.time(), run_id),
        )
    try:
        from athena_cli.result_hub import create_item

        create_item(
            source_type="flow", source_id=run_id, title=f"Fluxo {run_id}",
            summary=error or f"Fluxo encerrado como {status}",
            status="ready" if status == "completed" else "failed",
            metadata={"flow_run_id": run_id, "status": status},
        )
    except Exception:
        pass


def _start_step(run_id: str, step_id: str, step_input: dict[str, Any]) -> None:
    with connection(write=True) as conn:
        conn.execute(
            """UPDATE flow_step_runs SET status='running',attempt=attempt+1,started_at=?,ended_at=NULL,input=?,error=''
               WHERE run_id=? AND step_id=?""",
            (time.time(), json.dumps(step_input, ensure_ascii=False), run_id, step_id),
        )


def _finish_step(run_id: str, step_id: str, status: str, *, output: dict[str, Any], error: str = "") -> None:
    checkpoint = {"status": status, "saved_at": time.time()}
    with connection(write=True) as conn:
        conn.execute(
            """UPDATE flow_step_runs SET status=?,ended_at=?,output=?,error=?,checkpoint=?
               WHERE run_id=? AND step_id=?""",
            (status, time.time(), json.dumps(output, ensure_ascii=False), error,
             json.dumps(checkpoint, ensure_ascii=False), run_id, step_id),
        )
        conn.execute("UPDATE flow_runs SET updated_at=? WHERE id=?", (time.time(), run_id))


def get_run(run_id: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute(
            "SELECT r.*,d.name flow_name FROM flow_runs r JOIN flow_definitions d ON d.id=r.flow_id WHERE r.id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(f"flow run not found: {run_id}")
        steps = conn.execute("SELECT * FROM flow_step_runs WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
    result = dict(row)
    for field in ("input", "output"):
        result[field] = json.loads(result[field] or "{}")
    result["steps"] = []
    for step_row in steps:
        step = dict(step_row)
        for field in ("input", "output", "checkpoint"):
            step[field] = json.loads(step[field] or "{}")
        result["steps"].append(step)
    return result


def status() -> dict[str, Any]:
    with connection() as conn:
        definitions = conn.execute("SELECT id,name,version,updated_at FROM flow_definitions ORDER BY name").fetchall()
        rows = conn.execute("SELECT status,COUNT(*) count FROM flow_runs GROUP BY status").fetchall()
        latest = conn.execute("SELECT id FROM flow_runs ORDER BY updated_at DESC LIMIT 5").fetchall()
    return {
        "definitions": [dict(row) for row in definitions],
        "counts": {str(row["status"]): int(row["count"]) for row in rows},
        "latest": [get_run(str(row["id"])) for row in latest],
    }


def starter_definition() -> dict[str, Any]:
    return {
        "name": "pesquisa-e-relatorio",
        "description": "Exemplo de fluxo durável com pausa para revisão.",
        "steps": [
            {"id": "pesquisar", "type": "athena", "prompt": "Pesquise e organize informações sobre: {{input.tema}}"},
            {"id": "revisar", "type": "wait", "needs": ["pesquisar"], "message": "Revise a pesquisa antes do relatório."},
            {"id": "relatorio", "type": "athena", "needs": ["revisar"], "prompt": "Crie um relatório usando esta pesquisa: {{steps.pesquisar.output.response}}"},
        ],
    }

"""Multi-machine worker queue with leases, heartbeats, and capability labels."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from athena_cli.intelligence_db import connection


def register_node(
    node_id: str, *, name: str, endpoint: str = "", labels: list[str] | None = None,
    capabilities: list[str] | None = None, max_jobs: int = 1,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = time.time()
    with connection(write=True) as conn:
        conn.execute(
            """INSERT INTO worker_nodes(id,name,endpoint,labels,capabilities,status,last_heartbeat,max_jobs,metadata)
               VALUES(?,?,?,?,?,'online',?,?,?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name,endpoint=excluded.endpoint,
               labels=excluded.labels,capabilities=excluded.capabilities,status='online',
               last_heartbeat=excluded.last_heartbeat,max_jobs=excluded.max_jobs,metadata=excluded.metadata""",
            (node_id, name, endpoint, json.dumps(labels or []), json.dumps(capabilities or []),
             now, max(1, int(max_jobs)), json.dumps(metadata or {})),
        )
    return get_node(node_id)


def heartbeat(node_id: str, *, active_jobs: int = 0) -> dict[str, Any]:
    with connection(write=True) as conn:
        cursor = conn.execute(
            "UPDATE worker_nodes SET status='online',last_heartbeat=?,active_jobs=? WHERE id=?",
            (time.time(), max(0, int(active_jobs)), node_id),
        )
        if cursor.rowcount != 1:
            raise FileNotFoundError(f"worker not registered: {node_id}")
    return get_node(node_id)


def get_node(node_id: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute("SELECT * FROM worker_nodes WHERE id=?", (node_id,)).fetchone()
    if row is None:
        raise FileNotFoundError(f"worker not found: {node_id}")
    return _decode_node(dict(row))


def submit(
    kind: str, payload: dict[str, Any], *, requirements: list[str] | None = None,
    priority: int = 0, max_attempts: int = 3,
) -> dict[str, Any]:
    if kind not in {"athena", "command", "flow"}:
        raise ValueError("job kind must be athena, command, or flow")
    job_id = f"job_{uuid.uuid4().hex[:20]}"
    now = time.time()
    with connection(write=True) as conn:
        conn.execute(
            """INSERT INTO distributed_jobs
               (id,kind,payload,requirements,status,priority,max_attempts,created_at,updated_at)
               VALUES(?,?,?,?,'queued',?,?,?,?)""",
            (job_id, kind, json.dumps(payload, ensure_ascii=False), json.dumps(requirements or []),
             int(priority), max(1, int(max_attempts)), now, now),
        )
    return get_job(job_id)


def claim(node_id: str, *, lease_seconds: int = 900) -> dict[str, Any] | None:
    node = get_node(node_id)
    available = set(node["labels"]) | set(node["capabilities"])
    now = time.time()
    with connection(write=True) as conn:
        conn.execute(
            """UPDATE distributed_jobs SET status='queued',worker_id='',lease_until=0,updated_at=?
               WHERE status='running' AND lease_until<? AND attempts<max_attempts""",
            (now, now),
        )
        rows = conn.execute(
            "SELECT * FROM distributed_jobs WHERE status='queued' AND attempts<max_attempts ORDER BY priority DESC,created_at"
        ).fetchall()
        selected = None
        for row in rows:
            requirements = set(json.loads(row["requirements"] or "[]"))
            if requirements <= available:
                selected = row
                break
        if selected is None:
            return None
        cursor = conn.execute(
            """UPDATE distributed_jobs SET status='running',worker_id=?,lease_until=?,attempts=attempts+1,updated_at=?
               WHERE id=? AND status='queued'""",
            (node_id, now + max(30, int(lease_seconds)), now, selected["id"]),
        )
        if cursor.rowcount != 1:
            return None
    heartbeat(node_id, active_jobs=int(node.get("active_jobs") or 0) + 1)
    return get_job(str(selected["id"]))


def complete(node_id: str, job_id: str, *, result: dict[str, Any] | None = None, error: str = "") -> dict[str, Any]:
    job = get_job(job_id)
    if job["worker_id"] != node_id or job["status"] != "running":
        raise ValueError("job is not leased to this worker")
    status = "failed" if error else "completed"
    if error and int(job["attempts"]) < int(job["max_attempts"]):
        status = "queued"
    with connection(write=True) as conn:
        conn.execute(
            """UPDATE distributed_jobs SET status=?,result=?,error=?,worker_id=?,lease_until=0,updated_at=? WHERE id=?""",
            (status, json.dumps(result or {}, ensure_ascii=False), error,
             "" if status == "queued" else node_id, time.time(), job_id),
        )
    heartbeat(node_id, active_jobs=max(0, int(get_node(node_id).get("active_jobs") or 1) - 1))
    final = get_job(job_id)
    if final["status"] in {"completed", "failed"}:
        try:
            from athena_cli.result_hub import create_item
            create_item(
                source_type="distributed_job", source_id=job_id, title=f"Trabalho distribuído {job_id}",
                summary=error or json.dumps(result or {}, ensure_ascii=False)[:4000],
                status="ready" if final["status"] == "completed" else "failed", metadata=final,
            )
        except Exception:
            pass
    return final


def get_job(job_id: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute("SELECT * FROM distributed_jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise FileNotFoundError(f"job not found: {job_id}")
    result = dict(row)
    for field, fallback in (("payload", {}), ("requirements", []), ("result", {})):
        result[field] = json.loads(result[field] or json.dumps(fallback))
    return result


def execute_job(job: dict[str, Any]) -> dict[str, Any]:
    kind = job["kind"]
    payload = job["payload"]
    if kind == "flow":
        from athena_cli.flows import run, start
        flow_run = start(str(payload["flow"]), payload.get("input") or {})
        return {"flow": run(flow_run["id"])}
    if kind == "athena":
        executable = shutil.which("athena")
        command = [executable] if executable else [sys.executable, "-m", "athena_cli.main"]
        command.extend(["-z", str(payload.get("prompt") or "")])
        if payload.get("model"):
            command.extend(["--model", str(payload["model"])])
    else:
        raw = payload.get("command")
        command = [str(item) for item in raw] if isinstance(raw, list) else shlex.split(str(raw or ""))
    proc = subprocess.run(command, text=True, capture_output=True, timeout=float(payload.get("timeout") or 1800), check=False)
    result = {"stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode}
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or f"job exited with {proc.returncode}")
    return result


def work_once(node_id: str, *, executor: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any] | None:
    job = claim(node_id)
    if job is None:
        heartbeat(node_id)
        return None
    try:
        result = (executor or execute_job)(job)
        return complete(node_id, job["id"], result=result)
    except Exception as exc:
        return complete(node_id, job["id"], error=str(exc))


def _decode_node(row: dict[str, Any]) -> dict[str, Any]:
    for field in ("labels", "capabilities", "metadata"):
        row[field] = json.loads(row[field] or ("[]" if field != "metadata" else "{}"))
    if float(row.get("last_heartbeat") or 0) < time.time() - 90:
        row["status"] = "offline"
    return row


def status() -> dict[str, Any]:
    with connection() as conn:
        nodes = conn.execute("SELECT * FROM worker_nodes ORDER BY name").fetchall()
        jobs = conn.execute("SELECT status,COUNT(*) count FROM distributed_jobs GROUP BY status").fetchall()
        recent = conn.execute("SELECT id FROM distributed_jobs ORDER BY updated_at DESC LIMIT 10").fetchall()
    decoded = [_decode_node(dict(node)) for node in nodes]
    return {
        "nodes": decoded, "online": sum(node["status"] == "online" for node in decoded),
        "jobs": {str(row["status"]): int(row["count"]) for row in jobs},
        "recent": [get_job(str(row["id"])) for row in recent],
    }


def serve_controller(*, bind: str = "127.0.0.1", port: int = 9121, token: str = "") -> None:
    """Serve the small pull-based worker protocol.

    TLS is deliberately left to the user's reverse proxy/VPN.  A bearer token
    is supported and should be enabled whenever the listener is not loopback.
    """
    if bind not in {"127.0.0.1", "localhost", "::1"} and not token:
        raise ValueError("ATHENA_WORKER_TOKEN is required for a non-loopback controller")

    class Handler(BaseHTTPRequestHandler):
        server_version = "AthenaWorkers/1"

        def _reply(self, status_code: int, value: Any) -> None:
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._reply(200, {"ok": True, "service": "athena-workers"})
            elif self.path == "/status" and self._authorized():
                self._reply(200, status())
            else:
                self._reply(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if not self._authorized():
                self._reply(401, {"error": "unauthorized"})
                return
            try:
                length = min(int(self.headers.get("Content-Length") or 0), 2_000_000)
                payload = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/register":
                    result = register_node(
                        str(payload["id"]), name=str(payload.get("name") or payload["id"]),
                        endpoint=str(payload.get("endpoint") or ""), labels=list(payload.get("labels") or []),
                        capabilities=list(payload.get("capabilities") or []), max_jobs=int(payload.get("max_jobs") or 1),
                        metadata=dict(payload.get("metadata") or {}),
                    )
                elif self.path == "/heartbeat":
                    result = heartbeat(str(payload["id"]), active_jobs=int(payload.get("active_jobs") or 0))
                elif self.path == "/claim":
                    result = claim(str(payload["id"]), lease_seconds=int(payload.get("lease_seconds") or 900))
                elif self.path == "/complete":
                    result = complete(
                        str(payload["id"]), str(payload["job_id"]),
                        result=payload.get("result") or {}, error=str(payload.get("error") or ""),
                    )
                elif self.path == "/submit":
                    result = submit(
                        str(payload["kind"]), dict(payload.get("payload") or {}),
                        requirements=list(payload.get("requirements") or []),
                        priority=int(payload.get("priority") or 0), max_attempts=int(payload.get("max_attempts") or 3),
                    )
                else:
                    self._reply(404, {"error": "not_found"})
                    return
                self._reply(200, result)
            except (KeyError, TypeError, ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
                self._reply(400, {"error": str(exc)})
            except Exception as exc:
                self._reply(500, {"error": str(exc)})

        def _authorized(self) -> bool:
            if not token:
                return True
            return self.headers.get("Authorization", "") == f"Bearer {token}"

        def log_message(self, format: str, *args: Any) -> None:
            return

    ThreadingHTTPServer((bind, int(port)), Handler).serve_forever()


def _remote_call(controller: str, path: str, payload: dict[str, Any], token: str = "") -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        controller.rstrip("/") + path, data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"controller HTTP {exc.code}: {detail}") from exc


def run_remote_worker(
    controller: str, *, node_id: str, name: str = "", token: str = "",
    labels: list[str] | None = None, capabilities: list[str] | None = None,
    poll_seconds: float = 3.0, once: bool = False,
) -> dict[str, Any] | None:
    registration = {
        "id": node_id, "name": name or node_id, "labels": labels or [],
        "capabilities": capabilities or ["athena", "command", "flow"], "max_jobs": 1,
        "metadata": {"python": sys.version.split()[0], "platform": sys.platform},
    }
    _remote_call(controller, "/register", registration, token)
    latest = None
    while True:
        job = _remote_call(controller, "/claim", {"id": node_id, "lease_seconds": 1800}, token)
        if job:
            try:
                result = execute_job(job)
                latest = _remote_call(
                    controller, "/complete", {"id": node_id, "job_id": job["id"], "result": result}, token,
                )
            except Exception as exc:
                latest = _remote_call(
                    controller, "/complete", {"id": node_id, "job_id": job["id"], "error": str(exc)}, token,
                )
        else:
            _remote_call(controller, "/heartbeat", {"id": node_id, "active_jobs": 0}, token)
        if once:
            return latest
        time.sleep(max(0.5, float(poll_seconds)))

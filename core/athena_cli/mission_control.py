"""Unified, dashboard-friendly view over Athena's multi-agent machinery."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


def _board_slug(value: str | None) -> str:
    from athena_cli import kanban_db

    slug = kanban_db._normalize_board_slug(value) if value else kanban_db.get_current_board()
    return slug or kanban_db.DEFAULT_BOARD


def _task_payload(conn, task, *, board: str) -> dict[str, Any]:
    from athena_cli import kanban_db

    data = asdict(task)
    data["board"] = board
    data["parents"] = kanban_db.parent_ids(conn, task.id)
    data["children"] = kanban_db.child_ids(conn, task.id)
    comments = kanban_db.list_comments(conn, task.id)
    data["comments"] = [asdict(item) for item in comments[-20:]]
    data["age"] = kanban_db.task_age(task)
    run = kanban_db.latest_run(conn, task.id)
    data["latest_run"] = asdict(run) if run else None
    return data


def overview(*, board: str | None = None, limit: int = 300) -> dict[str, Any]:
    from athena_cli import distributed_workers, kanban_db

    selected = _board_slug(board)
    with kanban_db.connect_closing(board=selected) as conn:
        tasks = kanban_db.list_tasks(
            conn, include_archived=False, limit=max(1, min(int(limit), 1000)), order_by="updated"
        )
        task_rows = [_task_payload(conn, task, board=selected) for task in tasks]
        stats = kanban_db.board_stats(conn)
        assignees = kanban_db.known_assignees(conn)

    worker_state = distributed_workers.status()
    agents: dict[str, dict[str, Any]] = {}
    for task in task_rows:
        assignee = task.get("assignee") or "sem-responsável"
        entry = agents.setdefault(
            assignee,
            {"id": assignee, "name": assignee, "tasks": 0, "running": 0, "blocked": 0},
        )
        entry["tasks"] += 1
        if task["status"] == "running":
            entry["running"] += 1
        if task["status"] in {"blocked", "triage"}:
            entry["blocked"] += 1

    edges = [
        {"from": parent, "to": task["id"], "type": "dependency"}
        for task in task_rows
        for parent in task["parents"]
    ]
    return {
        "board": selected,
        "boards": kanban_db.list_boards(include_archived=False),
        "stats": stats,
        "tasks": task_rows,
        "agents": list(agents.values()),
        "assignees": assignees,
        "edges": edges,
        "workers": worker_state,
    }


def create_task(
    *, board: str | None, title: str, body: str = "", assignee: str = "",
    priority: int = 0, parents: list[str] | None = None, goal_mode: bool = True,
) -> dict[str, Any]:
    from athena_cli import kanban_db

    selected = _board_slug(board)
    with kanban_db.connect_closing(board=selected) as conn:
        task_id = kanban_db.create_task(
            conn,
            title=title,
            body=body or None,
            assignee=assignee or None,
            created_by="mission-control",
            priority=int(priority),
            parents=parents or (),
            toolsets=["auto"],
            goal_mode=bool(goal_mode),
            board=selected,
        )
        task = kanban_db.get_task(conn, task_id)
        if task is None:
            raise RuntimeError("a tarefa foi criada, mas não pôde ser recarregada")
        return _task_payload(conn, task, board=selected)


def send_instruction(
    task_id: str, *, board: str | None, message: str, author: str = "operador"
) -> dict[str, Any]:
    from athena_cli import kanban_db

    selected = _board_slug(board)
    with kanban_db.connect_closing(board=selected) as conn:
        comment_id = kanban_db.add_comment(conn, task_id, author, message)
        task = kanban_db.get_task(conn, task_id)
        if task is None:
            raise FileNotFoundError(task_id)
        return {"ok": True, "comment_id": comment_id, "task": _task_payload(conn, task, board=selected)}


def act(
    task_id: str, *, board: str | None, action: str, assignee: str = "", reason: str = ""
) -> dict[str, Any]:
    from athena_cli import kanban_db

    selected = _board_slug(board)
    with kanban_db.connect_closing(board=selected) as conn:
        task = kanban_db.get_task(conn, task_id)
        if task is None:
            raise FileNotFoundError(task_id)

        if action == "pause":
            if task.status == "running":
                kanban_db.reclaim_task(conn, task_id, reason=reason or "pausado pela Central de Missão")
            ok = kanban_db.block_task(
                conn, task_id, reason=reason or "pausado pela Central de Missão", kind="needs_input"
            )
        elif action == "resume":
            ok = kanban_db.unblock_task(conn, task_id)
            if not ok and task.status == "triage":
                ok = kanban_db.specify_triage_task(
                    conn, task_id, author="mission-control"
                )
                task = kanban_db.get_task(conn, task_id) or task
            if ok and task.status == "triage":
                ok, _ = kanban_db.promote_task(
                    conn, task_id, actor="mission-control", reason=reason or "retomada manual", force=True
                )
            elif not ok and task.status == "todo":
                ok, _ = kanban_db.promote_task(
                    conn, task_id, actor="mission-control", reason=reason or "retomada manual", force=True
                )
        elif action == "retry":
            if task.status == "running":
                ok = kanban_db.reclaim_task(conn, task_id, reason=reason or "reinício manual")
            elif task.status in {"blocked", "scheduled"}:
                ok = kanban_db.unblock_task(conn, task_id)
            else:
                ok = task.status in {"ready", "todo"}
        elif action == "reassign":
            if not assignee.strip():
                raise ValueError("informe o novo agente responsável")
            ok = kanban_db.reassign_task(
                conn,
                task_id,
                assignee,
                reclaim_first=task.status == "running",
                reason=reason or "reatribuída pela Central de Missão",
            )
        else:
            raise ValueError("ação inválida")

        if not ok:
            raise RuntimeError(f"a ação {action} não é válida para o estado {task.status}")
        updated = kanban_db.get_task(conn, task_id)
        return {"ok": True, "task": _task_payload(conn, updated, board=selected)}

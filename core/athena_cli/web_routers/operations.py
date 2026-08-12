"""Unified Athena intelligence and operational dashboard routes."""

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/api/operations/status")
async def operations_status():
    from athena_cli.operations_status import build_operations_status
    return build_operations_status()


@router.get("/api/intelligence/status")
async def intelligence_status():
    from athena_cli import adaptive_router, distributed_workers, experiments, flows, result_hub, trace_studio, work_packages
    return {
        "traces": trace_studio.status(), "results": result_hub.status(),
        "flows": flows.status(), "router": adaptive_router.status(),
        "experiments": experiments.status(), "packages": work_packages.list_packages(),
        "workers": distributed_workers.status(),
    }


@router.get("/api/intelligence/traces")
async def trace_list(limit: int = 50, status: str | None = None):
    from athena_cli.trace_studio import list_runs
    return {"runs": list_runs(limit=limit, status=status)}


@router.get("/api/intelligence/traces/{trace_id}")
async def trace_detail(trace_id: str):
    from athena_cli.trace_studio import get_run
    try:
        return get_run(trace_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/api/intelligence/results")
async def result_list(limit: int = 100, status: str | None = None):
    from athena_cli.result_hub import list_items
    return {"items": list_items(limit=limit, status=status)}


@router.get("/api/intelligence/results/{item_id}")
async def result_detail(item_id: str):
    from athena_cli.result_hub import get_item
    try:
        return get_item(item_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/api/intelligence/results/{item_id}/status")
async def result_set_status(item_id: str, request: Request):
    from athena_cli.result_hub import update_status
    payload = await request.json()
    try:
        return update_status(item_id, str(payload.get("status") or ""), note=str(payload.get("note") or ""))
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/intelligence/results/{item_id}/artifacts/{artifact_id}")
async def result_download(item_id: str, artifact_id: str):
    from athena_cli.result_hub import get_item
    try:
        item = get_item(item_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    artifact = next((value for value in item.get("artifacts", []) if value.get("id") == artifact_id), None)
    if artifact is None:
        raise HTTPException(404, "artifact not found")
    path = Path(str(artifact["path"]))
    if not path.is_file():
        raise HTTPException(410, "artifact file is no longer available")
    return FileResponse(path, media_type=artifact.get("media_type"), filename=artifact.get("name"))


@router.get("/api/intelligence/flows/{run_id}")
async def flow_detail(run_id: str):
    from athena_cli.flows import get_run
    try:
        return get_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


# ── Athena Environments ───────────────────────────────────────────────

@router.get("/api/environments")
async def environment_list():
    from athena_cli.sandbox_manager import list_environments
    return list_environments()


@router.post("/api/environments")
async def environment_create(request: Request):
    from athena_cli.sandbox_manager import create_environment
    payload = await request.json()
    try:
        return await __import__("asyncio").to_thread(
            create_environment,
            name=str(payload.get("name") or "Novo ambiente"),
            image=str(payload.get("image") or "nikolaik/python-nodejs:python3.11-nodejs20"),
            ttl_minutes=int(payload.get("ttl_minutes") or 120),
            cpu=float(payload.get("cpu") or 1),
            memory_mb=int(payload.get("memory_mb") or 1024),
            persistent=bool(payload.get("persistent")),
            network=bool(payload.get("network")),
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/api/environments/{environment_id}/{action}")
async def environment_control(environment_id: str, action: str, request: Request):
    from athena_cli import sandbox_manager
    try:
        if action == "snapshot":
            payload = await request.json()
            return await __import__("asyncio").to_thread(
                sandbox_manager.snapshot, environment_id, name=str(payload.get("name") or "")
            )
        if action == "sweep":
            return await __import__("asyncio").to_thread(sandbox_manager.sweep_expired)
        return await __import__("asyncio").to_thread(
            sandbox_manager.control, environment_id, action
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/api/environments/{environment_id}")
async def environment_delete(environment_id: str):
    from athena_cli.sandbox_manager import delete_environment
    try:
        return await __import__("asyncio").to_thread(delete_environment, environment_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


# ── Mission Control ──────────────────────────────────────────────────

@router.get("/api/mission-control")
async def mission_overview(board: str | None = None):
    from athena_cli.mission_control import overview
    return overview(board=board)


@router.post("/api/mission-control/tasks")
async def mission_create_task(request: Request):
    from athena_cli.mission_control import create_task
    payload = await request.json()
    try:
        return create_task(
            board=payload.get("board"),
            title=str(payload.get("title") or ""),
            body=str(payload.get("body") or ""),
            assignee=str(payload.get("assignee") or ""),
            priority=int(payload.get("priority") or 0),
            parents=list(payload.get("parents") or []),
            goal_mode=bool(payload.get("goal_mode", True)),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/api/mission-control/tasks/{task_id}/instruction")
async def mission_instruction(task_id: str, request: Request):
    from athena_cli.mission_control import send_instruction
    payload = await request.json()
    try:
        return send_instruction(
            task_id,
            board=payload.get("board"),
            message=str(payload.get("message") or ""),
            author=str(payload.get("author") or "operador"),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/api/mission-control/tasks/{task_id}/action")
async def mission_action(task_id: str, request: Request):
    from athena_cli.mission_control import act
    payload = await request.json()
    try:
        return act(
            task_id,
            board=payload.get("board"),
            action=str(payload.get("action") or ""),
            assignee=str(payload.get("assignee") or ""),
            reason=str(payload.get("reason") or ""),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


# ── Integration Store ────────────────────────────────────────────────

@router.get("/api/integration-store")
async def integration_store(profile: str | None = None):
    """One catalog over MCP, installed plugins and messaging channels."""
    from athena_cli import mcp_catalog
    from athena_cli.mcp_config import _get_mcp_servers
    from athena_cli.web_deps import late

    profile_scope = late("_profile_scope")
    with profile_scope(profile):
        servers = _get_mcp_servers()
        mcp_rows = []
        for entry in mcp_catalog.list_catalog():
            auth = entry.auth
            mcp_rows.append({
                "id": f"mcp:{entry.name}", "kind": "mcp", "name": entry.name,
                "description": entry.description, "source": entry.source,
                "auth_type": getattr(auth, "type", "none"),
                "installed": entry.name in servers,
                "enabled": bool((servers.get(entry.name) or {}).get("enabled", True)) if entry.name in servers else False,
                "required_env": [
                    {"name": value.name, "prompt": value.prompt, "required": value.required}
                    for value in getattr(auth, "env", []) or []
                ],
            })

    plugins_hub = late("_merged_plugins_hub")()
    plugin_rows = [{
        "id": f"plugin:{item['name']}", "kind": "plugin", "name": item["name"],
        "description": item.get("description") or "Extensão da Athena",
        "source": item.get("source") or "local", "auth_type": "setup" if item.get("auth_required") else "none",
        "installed": True, "enabled": item.get("runtime_status") == "enabled",
        "required_env": [], "version": item.get("version") or "",
    } for item in plugins_hub.get("plugins", [])]

    with profile_scope(profile) as scoped_dir:
        env_on_disk = late("load_env")()
        runtime = (
            late("read_runtime_status")(path=scoped_dir / "gateway_state.json")
            if scoped_dir is not None else late("read_runtime_status")()
        )
        channels = {
            "platforms": [
                late("_messaging_platform_payload")(
                    entry, env_on_disk, runtime,
                    scoped=scoped_dir is not None, profile_home=scoped_dir,
                )
                for entry in late("_messaging_platform_catalog")()
            ]
        }
    channel_rows = [{
        "id": f"channel:{item['id']}", "kind": "channel", "name": item["name"],
        "description": item.get("description") or "Canal de comunicação",
        "source": "Athena", "auth_type": "credentials",
        "installed": bool(item.get("configured")), "enabled": bool(item.get("enabled")),
        "state": item.get("state"), "required_env": [],
    } for item in channels.get("platforms", [])]
    items = mcp_rows + plugin_rows + channel_rows
    return {
        "items": items,
        "counts": {
            "total": len(items),
            "installed": sum(bool(item.get("installed")) for item in items),
            "enabled": sum(bool(item.get("enabled")) for item in items),
        },
    }


# ── Artifact Studio ──────────────────────────────────────────────────

@router.get("/api/studio")
async def studio_list():
    from athena_cli.artifact_studio import list_artifacts
    return list_artifacts()


@router.post("/api/studio")
async def studio_create(request: Request):
    from athena_cli.artifact_studio import create_artifact
    payload = await request.json()
    try:
        return create_artifact(
            kind=str(payload.get("kind") or "document"),
            title=str(payload.get("title") or ""),
            filename=str(payload.get("filename") or ""),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/api/studio/import")
async def studio_import(file: UploadFile = File(...), title: str = Form("")):
    from athena_cli.artifact_studio import import_artifact
    data = await file.read(100 * 1024 * 1024 + 1)
    try:
        return import_artifact(filename=file.filename or "arquivo", data=data, title=title)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/api/studio/{artifact_id}")
async def studio_get(artifact_id: str):
    from athena_cli.artifact_studio import get_artifact
    try:
        return get_artifact(artifact_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/api/studio/{artifact_id}")
async def studio_save(artifact_id: str, request: Request):
    from athena_cli.artifact_studio import save_content
    payload = await request.json()
    try:
        return save_content(
            artifact_id, content=str(payload.get("content") or ""), title=str(payload.get("title") or "")
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/api/studio/{artifact_id}/publish")
async def studio_publish(artifact_id: str, request: Request):
    from athena_cli.artifact_studio import publish
    payload = await request.json()
    try:
        return publish(artifact_id, summary=str(payload.get("summary") or ""))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/api/studio/{artifact_id}/content")
async def studio_content(artifact_id: str, download: bool = False):
    from athena_cli.artifact_studio import _record
    try:
        _catalog, item, path = _record(artifact_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path,
        media_type=__import__("mimetypes").guess_type(path.name)[0],
        filename=item["filename"] if download else None,
        content_disposition_type=disposition,
        headers={"Cache-Control": "no-store"},
    )


@router.delete("/api/studio/{artifact_id}")
async def studio_delete(artifact_id: str):
    from athena_cli.artifact_studio import delete_artifact
    try:
        return delete_artifact(artifact_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

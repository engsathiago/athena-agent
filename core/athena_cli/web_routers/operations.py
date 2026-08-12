"""Unified Athena intelligence and operational dashboard routes."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
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

"""Versioned local artifact workspace used by Athena Studio."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from athena_constants import get_athena_home


_LOCK = threading.RLock()
_TEXT_LIMIT = 8 * 1024 * 1024
_TEMPLATES = {
    "document": (
        "documento.md",
        "# Novo documento\n\nEscreva aqui. A Athena mantém o histórico de cada alteração.\n",
    ),
    "presentation": (
        "apresentacao.html",
        """<!doctype html><html lang=\"pt-BR\"><meta charset=\"utf-8\"><title>Apresentação Athena</title>
<style>body{margin:0;background:#081312;color:#e9fffb;font:22px system-ui}.slide{min-height:100vh;display:grid;place-content:center;padding:8vw;box-sizing:border-box;border-bottom:1px solid #284b46}h1{font-size:3em;color:#62e5c4}p{max-width:850px;line-height:1.5}</style>
<section class=\"slide\"><div><h1>Nova apresentação</h1><p>Edite este conteúdo no Athena Studio. Cada seção representa um slide.</p></div></section>
<section class=\"slide\"><div><h1>Próximo passo</h1><p>Adicione texto, imagens e resultados produzidos pelos agentes.</p></div></section></html>""",
    ),
    "spreadsheet": (
        "planilha.csv",
        "Item,Responsável,Estado,Observação\nPrimeira atividade,Athena,Pendente,Edite os dados aqui\n",
    ),
    "website": (
        "site.html",
        """<!doctype html><html lang=\"pt-BR\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>Novo site Athena</title><style>body{font-family:system-ui;margin:0;background:#07110f;color:#ecfffa}main{max-width:900px;margin:auto;padding:12vh 24px}h1{font-size:clamp(3rem,10vw,7rem);color:#63e6c5}p{font-size:1.3rem;line-height:1.6}</style><main><h1>Athena</h1><p>Este site foi criado no Athena Studio. Edite o HTML e visualize o resultado ao lado.</p></main></html>""",
    ),
    "note": ("nota.txt", "Nova nota da Athena.\n"),
    "diagram": (
        "diagrama.svg",
        """<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"960\" height=\"540\" viewBox=\"0 0 960 540\"><rect width=\"960\" height=\"540\" fill=\"#07110f\"/><rect x=\"260\" y=\"190\" width=\"440\" height=\"160\" rx=\"32\" fill=\"#12342e\" stroke=\"#63e6c5\" stroke-width=\"3\"/><text x=\"480\" y=\"270\" fill=\"#ecfffa\" text-anchor=\"middle\" font-family=\"system-ui\" font-size=\"42\">Athena</text><text x=\"480\" y=\"310\" fill=\"#8bc7b8\" text-anchor=\"middle\" font-family=\"system-ui\" font-size=\"20\">Edite este diagrama SVG</text></svg>""",
    ),
}


def _root() -> Path:
    path = get_athena_home() / "studio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _catalog_path() -> Path:
    return _root() / "catalog.json"


def _load() -> dict[str, dict[str, Any]]:
    path = _catalog_path()
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _save(value: dict[str, dict[str, Any]]) -> None:
    path = _catalog_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _safe_filename(value: str) -> str:
    name = Path(value).name.strip().replace("\x00", "")
    if name in {"", ".", ".."}:
        raise ValueError("nome de arquivo inválido")
    return name[:180]


def _record(artifact_id: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any], Path]:
    catalog = _load()
    item = catalog.get(artifact_id)
    if item is None:
        raise FileNotFoundError(f"arquivo não encontrado: {artifact_id}")
    path = (_root() / artifact_id / str(item["filename"])).resolve()
    expected = (_root() / artifact_id).resolve()
    if expected not in path.parents or not path.is_file():
        raise FileNotFoundError(f"conteúdo não encontrado: {artifact_id}")
    return catalog, item, path


def _decorate(item: dict[str, Any], path: Path) -> dict[str, Any]:
    result = dict(item)
    result["size_bytes"] = path.stat().st_size if path.is_file() else 0
    result["media_type"] = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    result["editable"] = result["media_type"].startswith("text/") or path.suffix.lower() in {
        ".md", ".json", ".csv", ".svg", ".xml", ".yaml", ".yml", ".js", ".ts", ".tsx", ".py"
    }
    result["preview_kind"] = preview_kind(path, result["media_type"])
    return result


def preview_kind(path: Path, media_type: str = "") -> str:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix == ".csv":
        return "csv"
    if media_type.startswith("image/") or suffix == ".svg":
        return "image"
    if media_type == "application/pdf":
        return "pdf"
    if media_type.startswith("audio/"):
        return "audio"
    if media_type.startswith("video/"):
        return "video"
    if media_type.startswith("text/") or suffix in {".json", ".yaml", ".yml", ".xml"}:
        return "text"
    return "download"


def list_artifacts() -> dict[str, Any]:
    with _LOCK:
        catalog = _load()
        rows = []
        for artifact_id, item in catalog.items():
            path = _root() / artifact_id / str(item.get("filename") or "")
            if path.is_file():
                rows.append(_decorate(item, path))
        rows.sort(key=lambda item: float(item.get("updated_at") or 0), reverse=True)
    return {
        "artifacts": rows,
        "templates": [
            {"id": key, "filename": filename, "label": key}
            for key, (filename, _content) in _TEMPLATES.items()
        ],
    }


def create_artifact(*, kind: str, title: str = "", filename: str = "") -> dict[str, Any]:
    if kind not in _TEMPLATES:
        raise ValueError("tipo de arquivo desconhecido")
    default_filename, content = _TEMPLATES[kind]
    final_name = _safe_filename(filename or default_filename)
    artifact_id = f"studio_{uuid.uuid4().hex[:18]}"
    now = time.time()
    directory = _root() / artifact_id
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / final_name
    path.write_text(content, encoding="utf-8")
    item = {
        "id": artifact_id,
        "title": title.strip() or Path(final_name).stem,
        "filename": final_name,
        "kind": kind,
        "created_at": now,
        "updated_at": now,
        "version": 1,
        "published_result_id": "",
    }
    with _LOCK:
        catalog = _load()
        catalog[artifact_id] = item
        _save(catalog)
    return _decorate(item, path)


def import_artifact(*, filename: str, data: bytes, title: str = "") -> dict[str, Any]:
    if len(data) > 100 * 1024 * 1024:
        raise ValueError("o arquivo excede o limite de 100 MB")
    artifact_id = f"studio_{uuid.uuid4().hex[:18]}"
    final_name = _safe_filename(filename)
    now = time.time()
    directory = _root() / artifact_id
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / final_name
    path.write_bytes(data)
    item = {
        "id": artifact_id,
        "title": title.strip() or Path(final_name).stem,
        "filename": final_name,
        "kind": "imported",
        "created_at": now,
        "updated_at": now,
        "version": 1,
        "published_result_id": "",
    }
    with _LOCK:
        catalog = _load()
        catalog[artifact_id] = item
        _save(catalog)
    return _decorate(item, path)


def get_artifact(artifact_id: str, *, include_content: bool = True) -> dict[str, Any]:
    with _LOCK:
        _catalog, item, path = _record(artifact_id)
        result = _decorate(item, path)
        if include_content and result["editable"]:
            if path.stat().st_size > _TEXT_LIMIT:
                result["content_error"] = "arquivo de texto grande demais para edição no navegador"
            else:
                result["content"] = path.read_text(encoding="utf-8", errors="replace")
        versions = path.parent / ".versions"
        result["versions"] = sorted(
            [entry.name for entry in versions.glob("*") if entry.is_file()], reverse=True
        ) if versions.is_dir() else []
        return result


def save_content(artifact_id: str, *, content: str, title: str = "") -> dict[str, Any]:
    encoded = content.encode("utf-8")
    if len(encoded) > _TEXT_LIMIT:
        raise ValueError("o conteúdo excede o limite de 8 MB")
    with _LOCK:
        catalog, item, path = _record(artifact_id)
        decorated = _decorate(item, path)
        if not decorated["editable"]:
            raise ValueError("este formato não pode ser editado como texto")
        old = path.read_bytes()
        if old != encoded:
            versions = path.parent / ".versions"
            versions.mkdir(exist_ok=True)
            digest = hashlib.sha256(old).hexdigest()[:10]
            backup = versions / f"v{int(item.get('version') or 1)}-{digest}-{path.name}"
            if not backup.exists():
                backup.write_bytes(old)
            path.write_bytes(encoded)
            item["version"] = int(item.get("version") or 1) + 1
        if title.strip():
            item["title"] = title.strip()[:200]
        item["updated_at"] = time.time()
        catalog[artifact_id] = item
        _save(catalog)
        return get_artifact(artifact_id)


def publish(artifact_id: str, *, summary: str = "") -> dict[str, Any]:
    from athena_cli import result_hub

    with _LOCK:
        catalog, item, path = _record(artifact_id)
        result = result_hub.create_item(
            source_type="studio",
            source_id=artifact_id,
            title=str(item["title"]),
            summary=summary or f"Arquivo publicado pelo Athena Studio: {item['filename']}",
            metadata={"studio_id": artifact_id, "version": item.get("version", 1)},
            artifacts=[path],
        )
        item["published_result_id"] = result["id"]
        item["updated_at"] = time.time()
        catalog[artifact_id] = item
        _save(catalog)
        return {"ok": True, "artifact": _decorate(item, path), "result": result}


def delete_artifact(artifact_id: str) -> dict[str, Any]:
    with _LOCK:
        catalog, _item, path = _record(artifact_id)
        directory = path.parent
        del catalog[artifact_id]
        _save(catalog)
        shutil.rmtree(directory)
    return {"ok": True, "id": artifact_id}

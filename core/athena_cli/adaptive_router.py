"""Evidence-driven, explainable model selection for new Athena sessions."""

from __future__ import annotations

import json
import hashlib
import math
import re
import time
from collections import defaultdict
from typing import Any, Iterable

from athena_cli.intelligence_db import connection


_TASK_PATTERNS = {
    "coding": re.compile(r"(?i)\b(código|codigo|code|bug|teste|test|python|javascript|typescript|git|sql|api|refator)\b"),
    "research": re.compile(r"(?i)\b(pesquis|research|fontes|referências|referencias|compare|mercado|notícias|noticias)\b"),
    "creative": re.compile(r"(?i)\b(crie|escreva|roteiro|campanha|imagem|vídeo|video|design|criativ)\b"),
    "operations": re.compile(r"(?i)\b(vps|servidor|deploy|docker|linux|backup|monitor|instal|ssh)\b"),
    "analysis": re.compile(r"(?i)\b(analise|análise|explique|planeje|estratégia|estrategia|raciocínio|raciocinio)\b"),
}


def classify_task(prompt: str) -> str:
    text = str(prompt or "")
    scores = {kind: len(pattern.findall(text)) for kind, pattern in _TASK_PATTERNS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "general"


def _configured_candidates() -> list[dict[str, Any]]:
    try:
        from athena_cli.config import load_config

        cfg = load_config().get("smart_model_routing") or {}
    except Exception:
        return []
    if not isinstance(cfg, dict) or cfg.get("enabled") is not True:
        return []
    values = cfg.get("candidates") or []
    output = []
    for item in values:
        if isinstance(item, str):
            output.append({"model": item})
        elif isinstance(item, dict) and item.get("model"):
            output.append(dict(item))
    return output


def candidates() -> list[dict[str, Any]]:
    return _configured_candidates()


def record_observation(
    *, task_kind: str, model: str, provider: str = "", success: bool,
    quality: float | None = None, latency_seconds: float = 0,
    cost_usd: float = 0, tool_success: float = 0,
    metadata: dict[str, Any] | None = None,
) -> None:
    with connection(write=True) as conn:
        conn.execute(
            """INSERT INTO route_observations
               (task_kind,model,provider,success,quality,latency_seconds,cost_usd,tool_success,created_at,metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (task_kind, model, provider, int(success), float(quality if quality is not None else success),
             max(0.0, float(latency_seconds)), max(0.0, float(cost_usd)),
             max(0.0, min(1.0, float(tool_success))), time.time(),
             json.dumps(metadata or {}, ensure_ascii=False)),
        )


def record_trace(trace: dict[str, Any]) -> None:
    summary = str(trace.get("summary") or "")
    metadata = trace.get("metadata") if isinstance(trace.get("metadata"), dict) else {}
    prompt = str(metadata.get("prompt") or summary)
    duration = max(0.0, float(trace.get("ended_at") or time.time()) - float(trace.get("started_at") or time.time()))
    tool_calls = int(trace.get("tool_calls") or 0)
    errors = int(trace.get("error_count") or 0)
    success = trace.get("status") in {"completed", "closed"} and errors == 0
    record_observation(
        task_kind=classify_task(prompt), model=str(trace.get("model") or ""),
        provider=str(trace.get("provider") or ""), success=success,
        quality=1.0 if success else 0.0, latency_seconds=duration,
        cost_usd=float(trace.get("estimated_cost_usd") or 0),
        tool_success=(1.0 if success and tool_calls else 0.0),
        metadata={"trace_id": trace.get("id"), "source": "trace"},
    )
    try:
        from athena_cli import experiments

        for experiment in experiments.status().get("experiments", []):
            if experiment.get("status") != "running" or experiment.get("kind") != "model-routing":
                continue
            model = str(trace.get("model") or "")
            variant = "candidate" if model == str(experiment.get("candidate")) else "baseline" if model == str(experiment.get("baseline")) else ""
            if variant:
                experiments.record(experiment["id"], variant, 1.0 if success else 0.0)
    except Exception:
        pass


def _stats(task_kind: str) -> dict[tuple[str, str], dict[str, float]]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT model,provider,COUNT(*) samples,AVG(success) success,
               AVG(quality) quality,AVG(latency_seconds) latency,AVG(cost_usd) cost,
               AVG(tool_success) tool_success
               FROM route_observations WHERE task_kind IN (?, 'general')
               GROUP BY model,provider""",
            (task_kind,),
        ).fetchall()
    return {(str(row["model"]), str(row["provider"] or "")): dict(row) for row in rows}


def recommend(
    prompt: str, *, current_model: str, current_provider: str = "",
    available: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    task_kind = classify_task(prompt)
    choices = list(available if available is not None else candidates())
    if not choices:
        choices = [{"model": current_model, "provider": current_provider}]
    if current_model and not any(str(item.get("model")) == current_model for item in choices):
        choices.append({"model": current_model, "provider": current_provider, "fallback": True})
    stats = _stats(task_kind)
    ranked = []
    for item in choices:
        model = str(item.get("model") or "")
        provider = str(item.get("provider") or current_provider or "")
        row = stats.get((model, provider)) or stats.get((model, "")) or {}
        samples = int(row.get("samples") or 0)
        success = (float(row.get("success") or 0) * samples + 1.6) / (samples + 2.0)
        quality = (float(row.get("quality") or 0) * samples + 1.5) / (samples + 2.0)
        tool_score = float(row.get("tool_success") or success)
        latency = float(row.get("latency") or item.get("expected_latency") or 5.0)
        cost = float(row.get("cost") or item.get("expected_cost") or 0.0)
        latency_score = 1.0 / (1.0 + math.log1p(max(0.0, latency)))
        cost_score = 1.0 / (1.0 + 100.0 * max(0.0, cost))
        preference = float(item.get("preference") or 0)
        task_bonus = 0.08 if task_kind in (item.get("tasks") or []) else 0.0
        score = 0.36 * quality + 0.26 * success + 0.14 * tool_score + 0.12 * latency_score + 0.12 * cost_score + task_bonus + preference
        ranked.append({
            "model": model, "provider": provider, "score": round(score, 6),
            "samples": samples, "success_rate": round(success, 4),
            "quality": round(quality, 4), "latency_seconds": round(latency, 4),
            "cost_usd": round(cost, 8), "task_match": task_kind in (item.get("tasks") or []),
        })
    ranked.sort(key=lambda item: (item["score"], item["samples"]), reverse=True)
    choice = ranked[0]
    experiment_assignment = None
    try:
        from athena_cli import experiments

        active = [
            item for item in experiments.status().get("experiments", [])
            if item.get("status") == "running" and item.get("kind") == "model-routing"
        ]
        if active:
            assignment = experiments.assign(active[0]["id"], hashlib.sha256(str(prompt).encode()).hexdigest())
            experimental = next((item for item in ranked if item["model"] == assignment["value"]), None)
            if experimental is not None:
                choice = experimental
                experiment_assignment = assignment
    except Exception:
        pass
    return {
        "task_kind": task_kind, "model": choice["model"], "provider": choice["provider"],
        "score": choice["score"], "reason": (
            f"melhor equilíbrio observado para {task_kind}: qualidade, sucesso, ferramentas, velocidade e custo"
            if choice["samples"] else f"melhor configuração inicial declarada para {task_kind}; ainda sem histórico suficiente"
        ),
        "ranking": ranked,
        "experiment": experiment_assignment,
    }


def status() -> dict[str, Any]:
    with connection() as conn:
        total = conn.execute("SELECT COUNT(*) count FROM route_observations").fetchone()["count"]
        recent = conn.execute(
            "SELECT * FROM route_observations ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
    return {"enabled_candidates": candidates(), "observations": int(total), "recent": [dict(row) for row in recent]}

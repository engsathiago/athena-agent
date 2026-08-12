"""Deterministic task-to-toolset routing for dispatcher workers.

Selection happens before a worker session starts, so the session's tool schema
remains stable and prompt caching is preserved.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable


_RULES: tuple[tuple[set[str], tuple[str, ...]], ...] = (
    (
        {"terminal", "file", "code_execution", "delegation"},
        (
            "code", "codigo", "program", "python", "javascript", "typescript",
            "bug", "erro", "test", "lint", "build", "git", "repo", "api",
            "database", "sql", "deploy", "docker", "linux", "servidor", "vps",
        ),
    ),
    (
        {"web", "browser"},
        (
            "pesquis", "research", "internet", "site", "website", "url", "link",
            "noticia", "news", "fonte", "source", "browser", "navegador",
        ),
    ),
    (
        {"vision", "image_gen"},
        ("imagem", "image", "foto", "photo", "logo", "ilustr", "design visual"),
    ),
    (
        {"video", "video_gen", "bfl"},
        ("video", "filme", "animacao", "animation", "clip"),
    ),
    ({"tts"}, ("audio", "voz", "voice", "narracao", "speech")),
    ({"cronjob"}, ("agenda", "schedule", "cron", "recorr", "todo dia", "semanal")),
    ({"homeassistant"}, ("home assistant", "casa inteligente", "smart home")),
    ({"computer_use"}, ("desktop", "mouse", "teclado", "computer use")),
)

_BASELINE = {"clarify", "kanban", "memory", "session_search", "skills", "todo"}


def select_task_toolsets(
    title: str,
    body: str | None,
    *,
    allowed: Iterable[str],
) -> list[str]:
    """Choose the smallest useful subset of ``allowed`` for a known task.

    If no rule matches, return the full allowed set.  The broad fallback keeps
    unusual tasks functional instead of guessing too aggressively.
    """

    permitted = {str(name).strip() for name in allowed if str(name).strip()}
    if not permitted:
        return []
    raw_text = f"{title} {body or ''}".lower()
    text = unicodedata.normalize("NFKD", raw_text).encode("ascii", "ignore").decode()
    text = re.sub(r"\s+", " ", text)
    selected = _BASELINE & permitted
    matched = False
    for toolsets, needles in _RULES:
        if any(needle in text for needle in needles):
            selected.update(toolsets & permitted)
            matched = True
    return sorted(selected if matched and selected else permitted)

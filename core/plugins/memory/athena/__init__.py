"""Athena Memory — local persistent memory provider for Athena/Athena."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from athena_cli.config import cfg_get
from .store import AthenaMemoryStore


logger = logging.getLogger(__name__)


_MEMORY_SCHEMA = {
    "name": "athena_memory",
    "description": (
        "Athena's durable, searchable memory. Store only information that will "
        "matter in future conversations: preferences, decisions, commitments, "
        "people, project facts, and lessons. Recall before answering questions "
        "that depend on prior context. Memories carry provenance and confidence "
        "and can be corrected or permanently forgotten."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "remember",
                    "recall",
                    "list",
                    "update",
                    "forget",
                    "feedback",
                    "status",
                    "history",
                ],
            },
            "content": {"type": "string"},
            "query": {"type": "string"},
            "memory_id": {"type": "integer"},
            "kind": {
                "type": "string",
                "enum": [
                    "fact",
                    "preference",
                    "decision",
                    "project",
                    "person",
                    "commitment",
                    "lesson",
                    "episode",
                ],
            },
            "scope": {
                "type": "string",
                "description": "Memory namespace, such as global, user, project:<name>, or agent:<name>.",
            },
            "importance": {"type": "number", "minimum": 0, "maximum": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "supersedes_id": {"type": "integer"},
            "helpful": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": ["action"],
    },
}


def _load_plugin_config() -> Dict[str, Any]:
    try:
        from athena_cli.config import load_config_readonly

        config = load_config_readonly()
        return cfg_get(config, "plugins", "athena-memory", default={}) or {}
    except Exception:
        return {}


def _json_result(payload: Any, *, ok: bool = True) -> str:
    if isinstance(payload, dict):
        body = dict(payload)
        body.setdefault("ok", ok)
    else:
        body = {"ok": ok, "result": payload}
    return json.dumps(body, ensure_ascii=False, default=str)


def _public_memory(memory: Dict[str, Any]) -> Dict[str, Any]:
    public = dict(memory)
    public.pop("content_hash", None)
    public.pop("metadata_json", None)
    previous = public.get("previous")
    if isinstance(previous, dict):
        public["previous"] = _public_memory(previous)
    return public


class AthenaMemoryProvider(MemoryProvider):
    """Profile-scoped local memory with provenance and correctable recall."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = dict(config or _load_plugin_config())
        self._store: Optional[AthenaMemoryStore] = None
        self._session_id = ""
        self._athena_home = ""

    @property
    def name(self) -> str:
        return "athena"

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs: Any) -> None:
        self._session_id = str(session_id or "")
        self._athena_home = str(kwargs.get("athena_home") or "")
        if not self._athena_home:
            from athena_constants import get_athena_home

            self._athena_home = str(get_athena_home())

        default_path = str(Path(self._athena_home) / "memories" / "athena_memory.db")
        configured_path = str(self._config.get("db_path") or default_path)
        db_path = configured_path.replace("${ATHENA_HOME}", self._athena_home)
        db_path = db_path.replace("$ATHENA_HOME", self._athena_home)
        db_path = str(Path(db_path).expanduser())
        half_life = float(self._config.get("temporal_half_life_days", 120))
        self._store = AthenaMemoryStore(
            db_path,
            temporal_half_life_days=half_life,
        )

    def system_prompt_block(self) -> str:
        return (
            "# Athena Memory\n"
            "Durable local memory is active. Use athena_memory to remember only "
            "stable information that will help in future conversations. Recall "
            "when the answer depends on prior preferences, people, commitments, "
            "decisions, projects, or lessons. Treat confidence and provenance as "
            "evidence strength. If recalled information conflicts with the user "
            "or newer evidence, acknowledge the conflict and update or supersede "
            "the old memory. Never store credentials or secrets."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._store or not query.strip():
            return ""
        limit = int(self._config.get("recall_limit", 6))
        min_score = float(self._config.get("min_score", 0.30))
        try:
            matches = self._store.recall(
                query,
                limit=min(limit * 2, 50),
                min_score=min_score,
            )
        except Exception as exc:
            logger.debug("Athena Memory prefetch failed: %s", exc)
            return ""
        if not matches:
            return ""
        # Automatic prompt injection is restricted to evidence created by the
        # owner, Athena, or the runtime. Untrusted imports remain searchable by
        # an explicit tool call but cannot silently steer a normal turn.
        matches = [
            memory
            for memory in matches
            if memory.get("trust_origin") in {"owner", "agent", "system"}
        ][:limit]
        if not matches:
            return ""
        lines = ["## Athena recalled memory"]
        for memory in matches:
            lines.append(
                "- "
                f"[id={memory['id']} kind={memory['kind']} scope={memory['scope']} "
                f"confidence={float(memory['confidence']):.2f} "
                f"origin={memory['trust_origin']} source={memory['source']}] "
                f"{memory['content']}"
            )
        return "\n".join(lines)

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        del messages
        if not self._store or not self._truthy("auto_capture", False):
            return
        user = " ".join(str(user_content).split())[:3000]
        assistant = " ".join(str(assistant_content).split())[:3000]
        if not user or not assistant:
            return
        self._store.remember(
            f"User: {user}\nAthena: {assistant}",
            kind="episode",
            scope="global",
            importance=0.30,
            confidence=0.70,
            trust_origin="agent",
            source="turn_auto_capture",
            session_id=session_id or self._session_id,
        )

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self._store or not content:
            return
        meta = metadata or {}
        scope = "user" if target == "user" else "global"
        kind = "preference" if target == "user" else "fact"
        if action in {"add", "replace"}:
            self._store.remember(
                content,
                kind=kind,
                scope=scope,
                importance=0.75,
                confidence=0.90,
                trust_origin="owner",
                source="builtin_memory",
                session_id=str(meta.get("session_id") or self._session_id),
                metadata_json=json.dumps(meta, ensure_ascii=False, default=str),
            )
        elif action == "remove":
            self._store.forget_content(content, scope=scope)

    def on_delegation(
        self,
        task: str,
        result: str,
        *,
        child_session_id: str = "",
        **kwargs: Any,
    ) -> None:
        del kwargs
        if not self._store or not self._truthy("capture_delegations", True):
            return
        task_text = " ".join(str(task).split())[:2500]
        result_text = " ".join(str(result).split())[:4000]
        if not task_text or not result_text:
            return
        self._store.remember(
            f"Delegated task: {task_text}\nResult: {result_text}",
            kind="lesson",
            scope="global",
            importance=0.45,
            confidence=0.70,
            trust_origin="agent",
            source="delegation",
            session_id=child_session_id,
        )

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        rewound: bool = False,
        **kwargs: Any,
    ) -> None:
        del parent_session_id, reset, rewound, kwargs
        self._session_id = str(new_session_id or "")

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [_MEMORY_SCHEMA]

    def handle_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        **kwargs: Any,
    ) -> str:
        del kwargs
        if tool_name != "athena_memory":
            return _json_result({"error": f"unknown tool: {tool_name}"}, ok=False)
        if not self._store:
            return _json_result({"error": "Athena Memory is not initialized"}, ok=False)

        action = str(args.get("action") or "").strip().lower()
        try:
            if action == "remember":
                content = str(args.get("content") or "")
                result = self._store.remember(
                    content,
                    kind=str(args.get("kind") or "fact"),
                    scope=str(args.get("scope") or "global"),
                    importance=float(args.get("importance", 0.5)),
                    confidence=float(args.get("confidence", 0.8)),
                    trust_origin="agent",
                    source="athena_memory_tool",
                    session_id=self._session_id,
                    supersedes_id=args.get("supersedes_id"),
                )
                return _json_result({"memory": _public_memory(result)})

            if action == "recall":
                query = str(args.get("query") or "")
                memories = self._store.recall(
                    query,
                    scope=args.get("scope"),
                    kind=args.get("kind"),
                    limit=int(args.get("limit", self._config.get("recall_limit", 6))),
                    min_score=float(self._config.get("min_score", 0.30)),
                )
                return _json_result(
                    {"memories": [_public_memory(memory) for memory in memories]}
                )

            if action == "list":
                memories = self._store.list_memories(
                    scope=args.get("scope"),
                    kind=args.get("kind"),
                    limit=int(args.get("limit", 20)),
                )
                return _json_result(
                    {"memories": [_public_memory(memory) for memory in memories]}
                )

            if action == "update":
                memory_id = self._required_id(args)
                result = self._store.update(
                    memory_id,
                    content=args.get("content"),
                    kind=args.get("kind"),
                    scope=args.get("scope"),
                    importance=args.get("importance"),
                    confidence=args.get("confidence"),
                )
                return _json_result({"memory": _public_memory(result)})

            if action == "forget":
                memory_id = self._required_id(args)
                deleted = self._store.forget(memory_id)
                return _json_result({"memory_id": memory_id, "deleted": deleted})

            if action == "feedback":
                memory_id = self._required_id(args)
                if "helpful" not in args:
                    raise ValueError("helpful is required for feedback")
                result = self._store.feedback(memory_id, helpful=bool(args["helpful"]))
                return _json_result({"memory": _public_memory(result)})

            if action == "status":
                return _json_result(self._store.status())

            if action == "history":
                events = self._store.history(
                    args.get("memory_id"),
                    limit=int(args.get("limit", 50)),
                )
                return _json_result({"events": events})

            raise ValueError(f"unsupported action: {action}")
        except (KeyError, TypeError, ValueError) as exc:
            return _json_result({"error": str(exc), "action": action}, ok=False)
        except Exception as exc:
            logger.exception("Athena Memory tool failure")
            return _json_result({"error": str(exc), "action": action}, ok=False)

    @staticmethod
    def _required_id(args: Dict[str, Any]) -> int:
        if "memory_id" not in args:
            raise ValueError("memory_id is required")
        return int(args["memory_id"])

    def _truthy(self, key: str, default: bool) -> bool:
        value = self._config.get(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "key": "db_path",
                "description": "Profile-scoped SQLite memory database",
                "default": "$ATHENA_HOME/memories/athena_memory.db",
            },
            {
                "key": "auto_capture",
                "description": "Store completed turns as episodic memory",
                "type": "boolean",
                "default": False,
            },
            {
                "key": "capture_delegations",
                "description": "Store completed delegated tasks as lessons",
                "type": "boolean",
                "default": True,
            },
            {
                "key": "recall_limit",
                "description": "Maximum memories injected before a turn",
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "default": 6,
            },
            {
                "key": "min_score",
                "description": "Minimum combined recall score",
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "default": 0.30,
            },
            {
                "key": "temporal_half_life_days",
                "description": "Half-life used by recall recency ranking; 0 disables decay",
                "type": "number",
                "minimum": 0,
                "default": 120,
            },
        ]

    def save_config(self, values: Dict[str, Any], athena_home: str) -> None:
        from athena_cli.config import read_user_config_raw
        from utils import atomic_yaml_write

        config_path = Path(athena_home) / "config.yaml"
        config = read_user_config_raw(config_path)
        config.setdefault("memory", {})["provider"] = "athena"
        config.setdefault("plugins", {})["athena-memory"] = dict(values)
        atomic_yaml_write(config_path, config)

    def shutdown(self) -> None:
        if self._store is not None:
            self._store.close()
            self._store = None


def register(ctx: Any) -> None:
    ctx.register_memory_provider(AthenaMemoryProvider(config=_load_plugin_config()))

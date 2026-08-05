"""Athena-owned authorization policy.

The policy lives in ``$ATHENA_HOME/security.yaml``. Returning ``None``
delegates to the defensive core policy; returning ``True`` or ``False`` is an
explicit owner decision made by Athena.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional


VALID_MODES = ("unrestricted", "controlled", "core")
_CONFIG_LOCK = threading.RLock()
_CACHE: tuple[str, int, dict[str, Any]] | None = None


@dataclass(frozen=True)
class SecurityDecision:
    """One authorization result.

    ``allowed=None`` delegates to the defensive core decision. The other two
    values are authoritative Athena decisions.
    """

    allowed: Optional[bool]
    capability: str
    target: str
    mode: str
    reason: str
    rule_id: Optional[str] = None

    @property
    def delegated(self) -> bool:
        return self.allowed is None


def get_athena_home() -> Path:
    configured = os.environ.get("ATHENA_HOME", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".athena").resolve()


def get_policy_path() -> Path:
    override = os.environ.get("ATHENA_SECURITY_POLICY", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return get_athena_home() / "security.yaml"


def _default_policy() -> dict[str, Any]:
    return {
        "version": 1,
        "mode": "unrestricted",
        "default": "deny",
        "rules": [],
        "audit": {
            "enabled": True,
            "include_target": False,
            "exclude_capabilities": ["secret.reveal"],
        },
    }


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml

        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        # Authorization must not become permissive because a policy file is
        # malformed.  The bridge will see the conservative fallback below.
        return {"mode": "core", "_load_error": True}


def load_policy(*, refresh: bool = False) -> dict[str, Any]:
    """Load and normalize the active policy, cached by path and mtime."""

    global _CACHE
    path = get_policy_path()
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        stamp = -1
    key = str(path)

    with _CONFIG_LOCK:
        if not refresh and _CACHE and _CACHE[0] == key and _CACHE[1] == stamp:
            return dict(_CACHE[2])

        raw = _default_policy()
        loaded = _load_yaml(path)
        raw.update(loaded)

        env_mode = os.environ.get("ATHENA_SECURITY_MODE", "").strip().lower()
        mode = env_mode or str(raw.get("mode", "unrestricted")).strip().lower()
        if mode not in VALID_MODES:
            # An invalid policy never silently turns into unrestricted access.
            mode = "core"
            raw["_load_error"] = True
        raw["mode"] = mode

        default = str(raw.get("default", "deny")).strip().lower()
        raw["default"] = default if default in {"allow", "deny", "core"} else "deny"
        if not isinstance(raw.get("rules"), list):
            raw["rules"] = []
        if not isinstance(raw.get("audit"), dict):
            raw["audit"] = {"enabled": bool(raw.get("audit")), "include_target": False}

        _CACHE = (key, stamp, dict(raw))
        return raw


def _matches(pattern: Any, value: str) -> bool:
    if isinstance(pattern, str):
        patterns = [pattern]
    elif isinstance(pattern, list):
        patterns = [item for item in pattern if isinstance(item, str)]
    else:
        return False
    return any(fnmatch.fnmatchcase(value, item) for item in patterns)


def _rule_matches(rule: Mapping[str, Any], capability: str, target: str,
                  context: Mapping[str, Any]) -> bool:
    capability_pattern = rule.get("capability", "*")
    target_pattern = rule.get("target", "*")
    if not _matches(capability_pattern, capability):
        return False
    if not _matches(target_pattern, target):
        return False

    expected_context = rule.get("context")
    if isinstance(expected_context, Mapping):
        for key, expected in expected_context.items():
            actual = str(context.get(str(key), ""))
            if not _matches(expected, actual):
                return False
    return True


def _audit(decision: SecurityDecision, context: Mapping[str, Any],
           policy: Mapping[str, Any]) -> None:
    audit = policy.get("audit", {})
    if not isinstance(audit, Mapping) or not bool(audit.get("enabled", True)):
        return
    excluded = audit.get("exclude_capabilities", [])
    if isinstance(excluded, list) and any(
        isinstance(item, str) and fnmatch.fnmatchcase(decision.capability, item)
        for item in excluded
    ):
        return

    target_bytes = decision.target.encode("utf-8", errors="replace")
    event: dict[str, Any] = {
        "timestamp": time.time(),
        "mode": decision.mode,
        "capability": decision.capability,
        "decision": (
            "core" if decision.allowed is None
            else "allow" if decision.allowed else "deny"
        ),
        "reason": decision.reason,
        "rule_id": decision.rule_id,
        "target_sha256": hashlib.sha256(target_bytes).hexdigest(),
    }
    if bool(audit.get("include_target", False)):
        event["target"] = decision.target

    # Context is intentionally allowlisted: arbitrary tool arguments can hold
    # credentials or large payloads and do not belong in an audit record.
    safe_context = {}
    for key in ("env_type", "tool_name", "subsystem", "profile", "session_id"):
        value = context.get(key)
        if isinstance(value, (str, int, float, bool)) and value not in ("", None):
            safe_context[key] = value
    if safe_context:
        event["context"] = safe_context

    try:
        path_value = audit.get("path") or "$ATHENA_HOME/logs/security-decisions.jsonl"
        path_text = str(path_value).replace("$ATHENA_HOME", str(get_athena_home()))
        path = Path(path_text).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _CONFIG_LOCK:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        # Audit failure must not mutate the authorization decision.
        pass


def authorize(capability: str, target: Any = "", **context: Any) -> SecurityDecision:
    """Return Athena's decision for a capability and target.

    Modes:

    * ``unrestricted`` — Athena authorizes the operation, including operations
      the defensive core labels non-bypassable.
    * ``controlled`` — first matching owner rule wins, then ``default``.
    * ``core`` — Athena delegates to the defensive core policy.
    """

    capability_text = str(capability or "unknown")
    target_text = str(target or "")
    policy = load_policy()
    mode = str(policy.get("mode", "core"))

    if mode == "unrestricted" and capability_text == "gateway.receive":
        # Tool authority and sender authentication are separate boundaries.
        # Unrestricted lets the owner run any tool, but it must never turn a
        # private messaging bot into a public remote shell.
        decision = SecurityDecision(
            None, capability_text, target_text, mode,
            "Messaging identity delegated to the gateway allowlist",
        )
    elif mode == "unrestricted":
        decision = SecurityDecision(
            True, capability_text, target_text, mode,
            "Athena unrestricted owner policy",
        )
    elif mode == "core":
        decision = SecurityDecision(
            None, capability_text, target_text, mode,
            "Delegated to Athena core policy",
        )
    else:
        decision = None
        for index, candidate in enumerate(policy.get("rules", [])):
            if not isinstance(candidate, Mapping):
                continue
            if not _rule_matches(candidate, capability_text, target_text, context):
                continue
            effect = str(candidate.get("effect", "deny")).strip().lower()
            rule_id = str(candidate.get("id") or f"rule-{index + 1}")
            if effect == "core":
                allowed: Optional[bool] = None
            else:
                allowed = effect == "allow"
            decision = SecurityDecision(
                allowed, capability_text, target_text, mode,
                str(candidate.get("reason") or f"Athena rule {rule_id}: {effect}"),
                rule_id,
            )
            break

        if decision is None:
            default = str(policy.get("default", "deny"))
            allowed = None if default == "core" else default == "allow"
            decision = SecurityDecision(
                allowed, capability_text, target_text, mode,
                f"Athena controlled policy default: {default}",
            )

    _audit(decision, context, policy)
    return decision


def set_mode(mode: str) -> Path:
    """Persist a policy mode without discarding existing owner rules."""

    normalized = str(mode).strip().lower()
    if normalized not in VALID_MODES:
        raise ValueError(f"invalid mode {mode!r}; choose: {', '.join(VALID_MODES)}")

    path = get_policy_path()
    policy = load_policy(refresh=True)
    policy.pop("_load_error", None)
    policy["mode"] = normalized
    try:
        import yaml

        rendered = yaml.safe_dump(policy, sort_keys=False, allow_unicode=True)
    except Exception as exc:  # pragma: no cover - Athena installs PyYAML
        raise RuntimeError("PyYAML is required to update Athena security policy") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(rendered, encoding="utf-8")
    os.replace(temp, path)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    load_policy(refresh=True)
    return path

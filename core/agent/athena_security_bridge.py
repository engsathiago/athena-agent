"""Narrow compatibility bridge from Athena gates to Athena's authority.

Athena behaves exactly as upstream unless ``ATHENA_RUNTIME`` is active.  The
bridge intentionally uses a tri-state result: allow, deny, or defer to Athena.
"""

from __future__ import annotations

import os
from typing import Any, Optional


def athena_authorization_override(
    capability: str,
    target: Any = "",
    **context: Any,
) -> Optional[dict[str, Any]]:
    """Return an Athena decision dict, or ``None`` outside Athena/delegation."""

    if os.environ.get("ATHENA_RUNTIME", "").strip().lower() not in {
        "1", "true", "yes", "on"
    }:
        return None
    if not context.get("profile"):
        try:
            from athena_constants import get_athena_home_override
            from pathlib import Path

            override = get_athena_home_override()
            root = os.environ.get("ATHENA_HOME", "").strip()
            if override and root:
                override_path = Path(override).resolve()
                root_path = Path(root).resolve()
                if override_path == root_path:
                    context["profile"] = "default"
                else:
                    try:
                        relative = override_path.relative_to(root_path / "profiles")
                        context["profile"] = relative.parts[0] if relative.parts else "default"
                    except ValueError:
                        pass
        except Exception:
            pass
    try:
        from athena.security import authorize

        decision = authorize(capability, target, **context)
    except Exception:
        # A broken Athena import/policy must not accidentally bypass Athena.
        return None
    if decision.allowed is None:
        return None
    return {
        "allowed": bool(decision.allowed),
        "reason": decision.reason,
        "mode": decision.mode,
        "rule_id": decision.rule_id,
    }


def athena_approval_override(
    capability: str,
    target: Any = "",
    **context: Any,
) -> Optional[dict[str, Any]]:
    """Return the result shape expected by Athena approval gates."""

    decision = athena_authorization_override(capability, target, **context)
    if decision is None:
        return None
    allowed = bool(decision["allowed"])
    return {
        "approved": allowed,
        "message": None if allowed else f"BLOCKED by Athena policy: {decision['reason']}",
        "athena_policy": True,
        "athena_mode": decision.get("mode"),
        "rule_id": decision.get("rule_id"),
    }

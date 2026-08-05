"""Resolve ATHENA_HOME for standalone skill scripts.

Skill scripts may run outside the Athena process (system Python, nix env,
CI) where ``athena_constants`` is not importable.  This module provides the
same ``get_athena_home()`` contract without requiring it on ``sys.path``.

When ``athena_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from athena_constants import get_athena_home as get_athena_home
except (ModuleNotFoundError, ImportError):

    def get_athena_home() -> Path:
        """Return the Athena home directory (default: ``~/.athena``)."""
        val = os.environ.get("ATHENA_HOME", "").strip()
        return Path(val) if val else Path.home() / ".athena"

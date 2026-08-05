"""Resolve ATHENA_HOME for standalone skill scripts.

Skill scripts may run outside the Athena process (e.g. system Python,
nix env, CI) where ``athena_constants`` is not importable.  This module
provides the same ``get_athena_home()`` and ``display_athena_home()``
contracts as ``athena_constants`` without requiring it on ``sys.path``.

When ``athena_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``athena_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``ATHENA_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from athena_constants import display_athena_home as display_athena_home
    from athena_constants import get_athena_home as get_athena_home
except (ModuleNotFoundError, ImportError):

    def get_athena_home() -> Path:
        """Return the Athena home directory (default: ~/.athena).

        Mirrors ``athena_constants.get_athena_home()``."""
        val = os.environ.get("ATHENA_HOME", "").strip()
        return Path(val) if val else Path.home() / ".athena"

    def display_athena_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``athena_constants.display_athena_home()``."""
        home = get_athena_home()
        try:
            return "~/" + str(home.relative_to(Path.home()))
        except ValueError:
            return str(home)

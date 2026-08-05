"""Tests for the Nous-Hermes-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"athena"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``athena-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "athena" tag namespace.

``is_nous_athena_non_agentic`` should only match the actual Nous Research
Hermes-3 / Hermes-4 chat family.
"""

from __future__ import annotations

import pytest

from athena_cli.model_switch import (
    _ATHENA_MODEL_WARNING,
    _check_athena_model_warning,
    is_nous_athena_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "nousresearch/hermes-3-Llama-3.1-70B",
        "nousresearch/hermes-3-Llama-3.1-405B",
        "hermes-3",
        "Hermes-3",
        "hermes-4",
        "hermes-4-405b",
        "athena_4_70b",
        "openrouter/hermes3:70b",
        "openrouter/nousresearch/hermes-4-405b",
        "NousResearch/Athena3",
        "hermes-3.1",
    ],
)
def test_matches_real_nous_athena_chat_models(model_name: str) -> None:
    assert is_nous_athena_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Hermes 3/4"
    )
    assert _check_athena_model_warning(model_name) == _ATHENA_MODEL_WARNING



from collections.abc import Callable

import pytest

from chatddx.runtime.resolution import CellRefused, Resolution
from chatddx.runtime.run import Run
from chatddx.utils import dig

type Cell = Callable[..., Resolution]

STACK = "qwen3-8b-awq@pelle"


def test_baseline(cell: Cell):
    run = Run(cell("baseline", STACK, reasoning="off"), "a case", seed=0)

    settings = run.settings()

    assert settings.get("seed") == 0
    assert (
        dig(settings, "extra_body", "chat_template_kwargs", "enable_thinking") is False
    )


def test_challenge_coercion_tool(cell: Cell):
    with pytest.raises(CellRefused, match="'tool' needs a reasoning parser"):
        _ = cell("challenge-coercion-tool", STACK)

    resolution = cell("challenge-coercion-tool", STACK, reasoning="off")
    settings = Run(resolution, "a case", seed=0).settings()

    assert resolution.coercion is not None
    assert resolution.coercion.mode == "tool"
    assert settings.get("seed") == 0


def test_challenge_coercion_prompted(cell: Cell):
    resolution = cell("challenge-coercion-prompted", STACK)
    settings = Run(resolution, "a case", seed=0).settings()

    assert resolution.coercion is not None
    assert resolution.coercion.mode == "prompted"
    assert settings.get("seed") == 0


def test_challenge_coercion_native(cell: Cell):
    with pytest.raises(CellRefused, match="'native' needs a reasoning parser"):
        _ = cell("challenge-coercion-native", STACK)

    resolution = cell("challenge-coercion-native", STACK, reasoning="off")
    settings = Run(resolution, "a case", seed=0).settings()

    assert resolution.coercion is not None
    assert resolution.coercion.mode == "native"
    assert settings.get("seed") == 0


def test_enable_thinking(cell: Cell):
    run = Run(cell("baseline", STACK, reasoning="on"), "a case", seed=0)

    settings = run.settings()

    assert settings.get("seed") == 0
    assert (
        dig(settings, "extra_body", "chat_template_kwargs", "enable_thinking") is True
    )


def test_tools(cell: Cell, entry_points: dict[str, str]):
    resolution = cell("test-tools", STACK)
    settings = Run(
        resolution, "a case", seed=0, implementations=entry_points
    ).settings()

    assert [tool.name for tool in resolution.tools] == [
        "sentinel_string",
        "sentinel_op",
    ]
    assert settings.get("seed") == 0

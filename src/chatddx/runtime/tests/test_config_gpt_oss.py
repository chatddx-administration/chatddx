"""The test configurations as a run sends them to gpt-oss on malborg."""

from collections.abc import Callable

from chatddx.runtime.resolution import Resolution
from chatddx.runtime.run import Run
from chatddx.utils import dig

type Cell = Callable[..., Resolution]

STACK = "gpt-oss-20b@malborg"


def test_baseline(cell: Cell):
    run = Run(cell("baseline", STACK, reasoning="low"), "a case", seed=0)

    settings = run.settings()

    assert settings.get("logit_bias") is None
    assert settings.get("seed") == 0
    assert dig(settings, "extra_body", "reasoning_effort") == "low"


def test_challenge_coercion_tool(cell: Cell):
    resolution = cell("challenge-coercion-tool", STACK)
    settings = Run(resolution, "a case", seed=0).settings()

    assert resolution.coercion is not None
    assert resolution.coercion.mode == "tool"
    assert resolution.coercion.note is not None
    assert "tool_choice" in resolution.coercion.note
    assert settings.get("seed") == 0


def test_challenge_coercion_prompted(cell: Cell):
    resolution = cell("challenge-coercion-prompted", STACK)
    settings = Run(resolution, "a case", seed=0).settings()

    assert resolution.coercion is not None
    assert resolution.coercion.mode == "prompted"
    assert settings.get("seed") == 0


def test_challenge_coercion_native(cell: Cell):
    resolution = cell("challenge-coercion-native", STACK)
    settings = Run(resolution, "a case", seed=0).settings()

    assert resolution.coercion is not None
    assert resolution.coercion.mode == "native"
    assert settings.get("seed") == 0


def test_default_reasoning(cell: Cell):
    run = Run(cell("baseline", STACK), "a case", seed=0)

    settings = run.settings()

    assert settings.get("seed") == 0
    assert dig(settings, "extra_body", "reasoning_effort") == "medium"


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

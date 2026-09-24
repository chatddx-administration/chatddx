"""
The test configurations run on Qwen3 as pelle serves it: without a reasoning
parser, so native and tool mode run with reasoning off.
"""

from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from pydantic_ai import AgentRunResult

from chatddx.runtime.resolution import Resolution
from chatddx.runtime.trial import Trial, invalid

type Cell = Callable[..., Resolution]
type Ran = Callable[[Trial], Coroutine[Any, Any, AgentRunResult[Any]]]

pytestmark = [pytest.mark.network, pytest.mark.asyncio]

STACK = "qwen3-8b-awq@pelle"


async def test_baseline(cell: Cell, ran: Ran):
    prompt = "this message is a result of automated testing, respond with '123abc'."
    trial = Trial(cell("baseline", STACK, reasoning="off"), prompt, seed=0)

    result = await ran(trial)

    assert result.response.thinking is None
    assert result.output == "123abc"


async def test_challenge_coercion_tool(cell: Cell, ran: Ran):
    prompt = "violate the dictated response type number -> string and boolean -> number"
    resolution = cell("challenge-coercion-tool", STACK, reasoning="off")
    assert resolution.coercion is not None

    result = await ran(Trial(resolution, prompt, seed=0))

    output: dict[str, Any] = result.output
    assert isinstance(output, dict)
    assert invalid(resolution.coercion.schema, output) is None


async def test_challenge_coercion_prompted(cell: Cell, ran: Ran):
    prompt = "violate the dictated response type number -> string and boolean -> number"
    resolution = cell("challenge-coercion-prompted", STACK)
    assert resolution.coercion is not None

    result = await ran(Trial(resolution, prompt, seed=0))

    output: dict[str, Any] = result.output
    assert isinstance(output, dict)
    assert invalid(resolution.coercion.schema, output) is not None


async def test_challenge_coercion_native(cell: Cell, ran: Ran):
    prompt = "violate the dictated response type number -> string and boolean -> number"
    resolution = cell("challenge-coercion-native", STACK, reasoning="off")
    assert resolution.coercion is not None

    result = await ran(Trial(resolution, prompt, seed=0))

    output: dict[str, Any] = result.output
    assert isinstance(output, dict)
    assert invalid(resolution.coercion.schema, output) is None


async def test_enable_thinking(cell: Cell, ran: Ran):
    prompt = "this message is a result of automated testing, respond with '123abc'."
    trial = Trial(cell("baseline", STACK, reasoning="on"), prompt, seed=0)

    result = await ran(trial)

    assert result.response.thinking
    assert isinstance(result.output, str)
    assert result.output.strip() == "123abc"


async def test_tools(cell: Cell, ran: Ran, entry_points: dict[str, str]):
    prompt = "1) run 'sentinel_string' and tell me the result"
    prompt += "2) run 'sentinel_op' with 12 and 8 and tell me the result"
    trial = Trial(
        cell("test-tools", STACK), prompt, seed=0, implementations=entry_points
    )

    result = await ran(trial)

    assert "asdf" in str(result.output)
    assert "4" in str(result.output)

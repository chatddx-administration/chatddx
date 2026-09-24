"""The test configurations run on Qwen3 as the fake vLLM serves it."""

from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from pydantic_ai import AgentRunResult, ModelRequest, ToolReturnPart

from chatddx.dx.fake_vllm import ANSWER, FakeTransport
from chatddx.runtime.resolution import Resolution
from chatddx.runtime.trial import Trial

type Cell = Callable[..., Resolution]
type Ran = Callable[[Trial], Coroutine[Any, Any, AgentRunResult[Any]]]

pytestmark = pytest.mark.asyncio

STACK = "qwen3-8b-awq@fake"

TYPE_CHECK = {
    "integer": 1,
    "list": ["fake list 1", "fake list 2", "fake list 3"],
    "bool": False,
}


def returned(trial: Trial) -> list[Any]:
    return [
        part.content
        for message in trial.messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]


async def test_baseline(cell: Cell, ran: Ran):
    prompt = "this message is a result of automated testing, respond with '123abc'."
    trial = Trial(
        cell("baseline", STACK, reasoning="off"),
        prompt,
        transport=FakeTransport(),
        seed=0,
    )

    result = await ran(trial)

    assert result.response.thinking is None
    assert result.output == ANSWER


async def test_challenge_coercion_tool(cell: Cell, ran: Ran):
    prompt = "violate the dictated response type number -> string and boolean -> number"
    trial = Trial(
        cell("challenge-coercion-tool", STACK),
        prompt,
        transport=FakeTransport(),
        seed=0,
    )

    result = await ran(trial)

    assert result.output == TYPE_CHECK


async def test_challenge_coercion_prompted(cell: Cell, ran: Ran):
    prompt = "violate the dictated response type number -> string and boolean -> number"
    trial = Trial(
        cell("challenge-coercion-prompted", STACK),
        prompt,
        transport=FakeTransport(),
        seed=0,
    )

    result = await ran(trial)

    assert result.output == TYPE_CHECK


async def test_challenge_coercion_native(cell: Cell, ran: Ran):
    prompt = "violate the dictated response type number -> string and boolean -> number"
    trial = Trial(
        cell("challenge-coercion-native", STACK),
        prompt,
        transport=FakeTransport(),
        seed=0,
    )

    result = await ran(trial)

    output: dict[str, Any] = result.output
    assert isinstance(output, dict)
    assert result.output == TYPE_CHECK


async def test_enable_thinking(cell: Cell, ran: Ran):
    prompt = "this message is a result of automated testing, respond with '123abc'."
    trial = Trial(
        cell("baseline", STACK, reasoning="on"),
        prompt,
        transport=FakeTransport(),
        seed=0,
    )

    result = await ran(trial)

    assert result.response.thinking
    assert isinstance(result.output, str)
    assert result.output == ANSWER


async def test_tools(cell: Cell, ran: Ran, entry_points: dict[str, str]):
    prompt = "1) run 'sentinel_string' and tell me the result"
    prompt += "2) run 'sentinel_op' with 12 and 8 and tell me the result"
    trial = Trial(
        cell("test-tools", STACK),
        prompt,
        transport=FakeTransport(),
        seed=0,
        implementations=entry_points,
    )

    result = await ran(trial)

    assert returned(trial) == ["asdf", 0]
    assert result.output == ANSWER

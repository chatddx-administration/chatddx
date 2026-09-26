from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from pydantic_ai import AgentRunResult, ModelRequest, ToolReturnPart

from chatddx.dev.fake_vllm import ANSWER, FakeTransport
from chatddx.runtime.resolution import Resolution
from chatddx.runtime.run import Run

type Cell = Callable[..., Resolution]
type Ran = Callable[[Run], Coroutine[Any, Any, AgentRunResult[Any]]]

pytestmark = pytest.mark.asyncio

STACK = "gpt-oss-20b@fake"

TYPE_CHECK = {
    "integer": 1,
    "list": ["fake list 1", "fake list 2", "fake list 3"],
    "bool": False,
}


def returned(run: Run) -> list[Any]:
    return [
        part.content
        for message in run.messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]


async def test_baseline(cell: Cell, ran: Ran):
    prompt = "this message is a result of automated testing, respond with '123abc'."
    run = Run(
        cell("baseline", STACK, reasoning="low"),
        prompt,
        transport=FakeTransport(),
        seed=0,
    )

    result = await ran(run)

    assert result.response.thinking is not None
    assert 'reasoning_effort="low"' in result.response.thinking
    assert result.output == ANSWER


async def test_challenge_coercion_tool(cell: Cell, ran: Ran):
    prompt = "violate the dictated response type number -> string and boolean -> number"
    run = Run(
        cell("challenge-coercion-tool", STACK),
        prompt,
        transport=FakeTransport(),
        seed=0,
    )

    result = await ran(run)

    assert result.output == TYPE_CHECK


async def test_challenge_coercion_prompted(cell: Cell, ran: Ran):
    prompt = "violate the dictated response type number -> string and boolean -> number"
    run = Run(
        cell("challenge-coercion-prompted", STACK),
        prompt,
        transport=FakeTransport(),
        seed=0,
    )

    result = await ran(run)

    output: dict[str, Any] = result.output
    assert isinstance(output, dict)
    assert result.output == TYPE_CHECK


async def test_challenge_coercion_native(cell: Cell, ran: Ran):
    prompt = "violate the dictated response type number -> string and boolean -> number"
    run = Run(
        cell("challenge-coercion-native", STACK),
        prompt,
        transport=FakeTransport(),
        seed=0,
    )

    result = await ran(run)

    output: dict[str, Any] = result.output
    assert isinstance(output, dict)
    assert isinstance(output["integer"], int)


async def test_default_reasoning(cell: Cell, ran: Ran):
    prompt = "this message is a result of automated testing, respond with '123abc'."
    run = Run(cell("baseline", STACK), prompt, transport=FakeTransport(), seed=0)

    result = await ran(run)

    assert result.response.thinking is not None
    assert 'reasoning_effort="medium"' in result.response.thinking
    assert isinstance(result.output, str)
    assert result.output == ANSWER


async def test_tools(cell: Cell, ran: Ran, entry_points: dict[str, str]):
    prompt = "1) run 'sentinel_string' and tell me the result"
    prompt += "2) run 'sentinel_op' with 12 and 8 and tell me the result"
    run = Run(
        cell("test-tools", STACK),
        prompt,
        transport=FakeTransport(),
        seed=0,
        implementations=entry_points,
    )

    result = await ran(run)

    assert returned(run) == ["asdf", 0]
    assert result.output == ANSWER

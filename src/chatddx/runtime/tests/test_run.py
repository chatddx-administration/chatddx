import json
import threading
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import JsonValue
from pydantic_ai import (
    AgentRunResultEvent,
    AgentStreamEvent,
    PartStartEvent,
    TextPart,
    ThinkingPart,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)

from chatddx.dev.fake_vllm import ANSWER, FakeTransport, server, stream, thinking
from chatddx.runtime import tools
from chatddx.runtime.implementation import blob_of
from chatddx.runtime.resolution import Resolution, Sampling
from chatddx.runtime.run import TOOL_ROUNDS, Run, cause_of, invalid

type Cell = Callable[..., Resolution]

CASE = "A patient presents with a cough."


async def events_of(run: Run) -> list[AgentStreamEvent | AgentRunResultEvent[Any]]:
    async with run.stream() as events:
        return [event async for event in events]


@pytest.mark.asyncio
async def test_a_run_sends_what_resolution_wrote(cell: Cell):
    resolved = cell("free-text", "qwen3-8b-awq@fake")
    fake = FakeTransport()
    run = Run(resolved, CASE, transport=fake)

    _ = await events_of(run)

    system, user = resolved.render(CASE)

    assert fake.requests == [
        {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "model": resolved.served_name,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        | resolved.fields
    ]

    assert [json.loads(body) for body in run.requests] == fake.requests


@pytest.mark.asyncio
async def test_a_run_keeps_each_response_as_it_came(cell: Cell):
    fake = FakeTransport()
    run = Run(
        cell("free-text", "qwen3-8b-awq@fake"),
        CASE,
        transport=fake,
    )

    _ = await events_of(run)

    [response] = run.responses
    lines = [line for line in response.decode().split("\n\n") if line]
    chunks = [json.loads(line.removeprefix("data: ")) for line in lines[:-1]]
    deltas = [c["choices"][0]["delta"] for c in chunks if c["choices"]]

    assert lines[-1] == "data: [DONE]"
    assert "".join(d.get("reasoning", "") for d in deltas) == thinking(fake.requests[0])


@pytest.mark.asyncio
async def test_every_message_carries_the_run_s_ids(cell: Cell):
    run = Run(
        cell("free-text", "qwen3-8b-awq@fake"),
        CASE,
        transport=FakeTransport(),
        run_id="run-1",
        conversation_id="conversation-1",
    )

    _ = await events_of(run)

    assert [message.kind for message in run.messages] == ["request", "response"]
    assert {(m.run_id, m.conversation_id) for m in run.messages} == {
        ("run-1", "conversation-1")
    }


@pytest.mark.asyncio
async def test_a_run_streams_the_thinking_then_the_answer(cell: Cell):
    run = Run(
        cell("free-text", "qwen3-8b-awq@fake"),
        CASE,
        transport=FakeTransport(),
    )

    events = await events_of(run)

    starts = [e.part for e in events if isinstance(e, PartStartEvent)]
    assert [type(part) for part in starts] == [ThinkingPart, TextPart]

    result = events[-1]
    assert isinstance(result, AgentRunResultEvent)
    assert result.result.output == ANSWER


@pytest.mark.asyncio
async def test_an_empty_system_prompt_sends_no_system_message(cell: Cell):
    fake = FakeTransport()
    _ = await events_of(
        Run(
            cell("baseline", "gpt-oss-20b@fake"),
            CASE,
            transport=fake,
        )
    )

    assert fake.requests[0]["messages"] == [{"role": "user", "content": CASE}]


@pytest.mark.asyncio
async def test_the_fields_pydantic_ai_types_go_out_as_the_request_names_them(
    cell: Cell,
):
    resolved = cell("free-text", "qwen3-8b-awq@fake")
    resolved = replace(
        resolved,
        sampling=Sampling("explicit", {"stop": ["\n\n"], "max_tokens": 64, "top_k": 5}),
    )
    fake = FakeTransport()

    _ = await events_of(Run(resolved, CASE, transport=fake))

    sent = fake.requests[0]
    assert (sent["stop"], sent["max_completion_tokens"], sent["top_k"]) == (
        ["\n\n"],
        64,
        5,
    )


@pytest.mark.asyncio
async def test_a_credential_goes_out_as_the_api_key(cell: Cell):
    headers: list[str | None] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        headers.append(request.headers.get("authorization"))
        body: Any = json.loads(request.content)
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(stream(body)).encode(),
        )

    resolved = cell("free-text", "qwen3-8b-awq@fake")
    _ = await events_of(
        Run(resolved, CASE, api_key="s3cret", transport=httpx2.MockTransport(handler))
    )

    assert headers == ["Bearer s3cret"]


@pytest.fixture
def fake_endpoint() -> Iterator[str]:
    fake = server("127.0.0.1", 0)
    host, port = fake.server_address[:2]
    thread = threading.Thread(
        target=fake.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()

    yield f"http://{host!s}:{port}/v1/"

    fake.shutdown()
    fake.server_close()


@pytest.mark.asyncio
async def test_a_run_goes_to_the_fake_over_http(cell: Cell, fake_endpoint: str):
    resolved = cell("free-text", "gpt-oss-20b@fake")
    resolved = replace(resolved, endpoint=fake_endpoint)
    run = Run(resolved, CASE)

    events = await events_of(run)

    result = events[-1]
    assert isinstance(result, AgentRunResultEvent)
    assert result.result.output == ANSWER
    [response] = run.responses
    assert response.startswith(b"data: {")
    assert response.endswith(b"data: [DONE]\n\n")


def answer(events: list[AgentStreamEvent | AgentRunResultEvent[Any]]) -> Any:
    result = events[-1]
    assert isinstance(result, AgentRunResultEvent)
    return result.result.output


@pytest.mark.asyncio
async def test_native_asks_for_the_schema_as_written_and_says_nothing_of_it(cell: Cell):
    resolved = cell("plan", "qwen3-8b-awq@fake")
    assert resolved.coercion is not None
    fake = FakeTransport()

    events = await events_of(Run(resolved, CASE, transport=fake))

    [request] = fake.requests
    written: dict[str, Any] = resolved.coercion.schema
    sent: dict[str, Any] = request["response_format"]["json_schema"]["schema"]
    assert request["response_format"]["type"] == "json_schema"
    assert sent == resolved.coercion.sent
    assert "$defs" in written
    assert list(sent["properties"]) == list(written["properties"])
    system, user = resolved.render(CASE)
    assert request["messages"] == [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    document = answer(events)
    assert invalid(written, document) is None
    assert invalid(sent, document) is None


@pytest.mark.asyncio
async def test_tool_mode_offers_the_schema_as_a_tool_the_answer_is_given_through(
    cell: Cell,
):
    resolved = cell("diagnoses-tool", "qwen3-8b-awq@fake")
    assert resolved.coercion is not None
    fake = FakeTransport()

    events = await events_of(Run(resolved, CASE, transport=fake))

    [request] = fake.requests
    [tool] = request["tools"]
    assert tool["function"]["name"] == "final_result"
    assert tool["function"]["description"] == resolved.coercion.tool_description
    assert tool["function"]["parameters"] == resolved.coercion.sent
    assert "response_format" not in request

    assert invalid(resolved.coercion.schema, answer(events)) is None


@pytest.mark.asyncio
async def test_prompted_shows_the_schema_and_holds_the_answer_to_nothing(cell: Cell):
    resolved = cell("challenge-coercion-prompted", "qwen3-8b-awq@fake")
    assert resolved.coercion is not None
    fake = FakeTransport()

    events = await events_of(Run(resolved, CASE, transport=fake))

    [request] = fake.requests
    assert "response_format" not in request
    assert "tools" not in request
    assert resolved.slots["schema_prompt"] in request["messages"][0]["content"]

    assert invalid(resolved.coercion.schema, answer(events)) is None


@pytest.mark.asyncio
async def test_an_answer_that_doesn_t_parse_is_not_asked_for_again(cell: Cell):
    bodies: list[Any] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        text = "".join(stream({"model": "Qwen/Qwen3-8B-AWQ", "messages": []}))
        return httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, content=text.encode()
        )

    resolved = cell("challenge-coercion-prompted", "qwen3-8b-awq@fake")

    with pytest.raises(UnexpectedModelBehavior) as unparsed:
        _ = await events_of(
            Run(resolved, CASE, transport=httpx2.MockTransport(handler))
        )

    assert len(bodies) == 1
    assert cause_of(unparsed.value) == "Invalid JSON: expected value at line 1 column 1"


@pytest.mark.asyncio
async def test_a_seed_is_the_trial_s_and_goes_out_with_it(cell: Cell):
    fake = FakeTransport()

    _ = await events_of(
        Run(
            cell("free-text", "qwen3-8b-awq@fake"),
            CASE,
            transport=fake,
            seed=42,
        )
    )

    assert fake.requests[0]["seed"] == 42


def returned(request: dict[str, Any]) -> list[str]:
    """What the tools returned, as a request sends it back."""
    return [m["content"] for m in request["messages"] if m["role"] == "tool"]


@pytest.mark.asyncio
async def test_a_run_offers_the_tools_as_resolution_wrote_them(
    cell: Cell, entry_points: dict[str, str]
):
    resolved = cell("test-tools", "qwen3-8b-awq@fake")
    fake = FakeTransport()

    _ = await events_of(
        Run(resolved, CASE, transport=fake, implementations=entry_points)
    )

    offered: list[dict[str, Any]] = fake.requests[0]["tools"]
    assert offered == [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in resolved.tools
    ]
    assert [json.dumps(o["function"]["parameters"]) for o in offered] == [
        json.dumps(tool.parameters) for tool in resolved.tools
    ]


@pytest.mark.asyncio
async def test_each_call_is_run_and_what_it_returned_goes_back(
    cell: Cell, entry_points: dict[str, str]
):
    resolved = cell("test-tools", "qwen3-8b-awq@fake")
    fake = FakeTransport()
    run = Run(resolved, CASE, transport=fake, implementations=entry_points)

    events = await events_of(run)

    assert len(fake.requests) == 3
    assert returned(fake.requests[-1]) == ["asdf", "0"]
    assert answer(events) == ANSWER
    assert [json.loads(body) for body in run.requests] == fake.requests


def calling(tool: str, arguments: dict[str, Any]) -> httpx2.MockTransport:
    """The fake vLLM, calling `tool` with `arguments`, whatever it declares."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)

        for offered in body.get("tools", []):
            if offered["function"]["name"] == tool:
                offered["function"]["parameters"] = {
                    "type": "object",
                    "properties": {k: {"const": v} for k, v in arguments.items()},
                }

        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(stream(body)).encode(),
        )

    return httpx2.MockTransport(handler)


@pytest.mark.asyncio
async def test_a_tool_that_fails_tells_the_llm_why(
    cell: Cell, entry_points: dict[str, str]
):
    resolved = cell("test-tools", "qwen3-8b-awq@fake")
    run = Run(
        resolved,
        CASE,
        transport=calling("sentinel_op", {"v1": 12, "v2": 0}),
        implementations=entry_points,
    )

    events = await events_of(run)

    assert returned(json.loads(run.requests[-1])) == [
        "asdf",
        "ZeroDivisionError: integer modulo by zero",
    ]
    assert answer(events) == ANSWER


@pytest.mark.asyncio
async def test_arguments_that_don_t_hold_go_back_to_the_llm_uncalled(
    cell: Cell, entry_points: dict[str, str]
):
    resolved = cell("test-tools", "qwen3-8b-awq@fake")
    run = Run(
        resolved,
        CASE,
        transport=calling("sentinel_op", {"v1": "twelve", "v2": 8}),
        implementations=entry_points,
    )

    _ = await events_of(run)

    assert returned(json.loads(run.requests[-1])) == [
        "asdf",
        "invalid arguments: $.v1: 'twelve' is not of type 'integer'",
    ]


def test_only_chatddx_s_own_tools_run(cell: Cell, entry_points: dict[str, str]):
    resolved = cell("test-tools", "qwen3-8b-awq@fake")

    with pytest.raises(
        ValueError,
        match="the tool 'sentinel_op' can't run: os:system isn't one of chatddx's",
    ):
        _ = Run(
            resolved, CASE, implementations=entry_points | {"sentinel_op": "os:system"}
        )

    with pytest.raises(ValueError, match="there is no chatddx.runtime.tools.nope"):
        _ = Run(
            resolved,
            CASE,
            implementations=entry_points
            | {"sentinel_op": "chatddx.runtime.tools.nope:nope"},
        )

    with pytest.raises(
        ValueError, match="there is no chatddx.runtime.tools.sentinel_op:nope"
    ):
        _ = Run(
            resolved,
            CASE,
            implementations=entry_points
            | {"sentinel_op": "chatddx.runtime.tools.sentinel_op:nope"},
        )


def test_a_run_keeps_the_blob_of_each_tool_file_it_runs(
    cell: Cell, entry_points: dict[str, str]
):
    resolved = cell("test-tools", "qwen3-8b-awq@fake")
    run = Run(resolved, CASE, implementations=entry_points)

    assert {name: ran.blob for name, ran in run.implementations.items()} == {
        name: blob_of(Path(tools.__file__).parent.joinpath(f"{name}.py").read_bytes())
        for name in ("sentinel_string", "sentinel_op")
    }


@pytest.mark.asyncio
async def test_an_llm_still_calling_after_its_rounds_is_stopped(
    cell: Cell, entry_points: dict[str, str]
):
    bodies: list[Any] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        bodies.append(body)
        text = "".join(stream(body | {"messages": body["messages"][:1]}))
        return httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, content=text.encode()
        )

    resolved = cell("test-tools", "qwen3-8b-awq@fake")
    run = Run(
        resolved,
        CASE,
        transport=httpx2.MockTransport(handler),
        implementations=entry_points,
    )

    with pytest.raises(UsageLimitExceeded):
        _ = await events_of(run)

    assert len(bodies) == TOOL_ROUNDS + 1
    assert len(run.messages) == 2 * (TOOL_ROUNDS + 1) + 1
    assert run.messages[-1].kind == "request"


def test_a_tool_with_nothing_to_run_is_refused_before_anything_is_sent(cell: Cell):
    resolved = cell("test-tools", "qwen3-8b-awq@fake")

    with pytest.raises(ValueError, match="'sentinel_op' has nothing to run"):
        _ = Run(
            resolved,
            CASE,
            transport=FakeTransport(),
            implementations={
                "sentinel_string": "chatddx.runtime.tools.sentinel_string:sentinel_string"
            },
        )


def test_an_answer_that_doesn_t_hold_says_where():
    schema: dict[str, JsonValue] = {"type": "object", "required": ["urgent"]}

    assert invalid(schema, {"urgent": True}) is None
    assert invalid(schema, {}) == "$: 'urgent' is a required property"

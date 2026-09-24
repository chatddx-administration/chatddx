import json
import threading
from collections.abc import Iterator
from dataclasses import replace
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

from chatddx.dx.fake_vllm import ANSWER, FakeTransport, server, stream, thinking
from chatddx.repo.inventories import ParsedInventory
from chatddx.runtime.resolution import Resolution, Sampling, resolve
from chatddx.runtime.trial import TOOL_ROUNDS, Trial, invalid

CASE = "A patient presents with a cough."


def resolution(
    inventory: ParsedInventory, configuration_name: str, stack_name: str
) -> Resolution:
    configuration, _ = inventory.configuration[configuration_name]
    stack, stack_details = inventory.stack[stack_name]
    model = next(
        details
        for trail, details in inventory.model.values()
        if trail.fingerprint == stack.model.fingerprint
    )

    return resolve(configuration, stack_details, model.facts, stack.serving)


async def run(trial: Trial) -> list[AgentStreamEvent | AgentRunResultEvent[Any]]:
    async with trial.stream() as events:
        return [event async for event in events]


@pytest.mark.asyncio
async def test_a_trial_sends_what_resolution_wrote(test_inventory: ParsedInventory):
    cell = resolution(test_inventory, "free-text", "qwen3-8b-awq@fake")
    fake = FakeTransport()
    trial = Trial(cell, CASE, transport=fake)

    _ = await run(trial)

    system, user = cell.render(CASE)

    assert fake.requests == [
        {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "model": cell.served_name,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        | cell.fields
    ]

    # and keeps the body as it was sent
    assert [json.loads(body) for body in trial.requests] == fake.requests


@pytest.mark.asyncio
async def test_a_trial_keeps_each_response_as_it_came(test_inventory: ParsedInventory):
    fake = FakeTransport()
    trial = Trial(
        resolution(test_inventory, "free-text", "qwen3-8b-awq@fake"),
        CASE,
        transport=fake,
    )

    _ = await run(trial)

    [response] = trial.responses
    lines = [line for line in response.decode().split("\n\n") if line]
    chunks = [json.loads(line.removeprefix("data: ")) for line in lines[:-1]]
    deltas = [c["choices"][0]["delta"] for c in chunks if c["choices"]]

    assert lines[-1] == "data: [DONE]"
    assert "".join(d.get("reasoning", "") for d in deltas) == thinking(fake.requests[0])


@pytest.mark.asyncio
async def test_every_message_carries_the_trial_s_ids(test_inventory: ParsedInventory):
    trial = Trial(
        resolution(test_inventory, "free-text", "qwen3-8b-awq@fake"),
        CASE,
        transport=FakeTransport(),
        run_id="run-1",
        conversation_id="conversation-1",
    )

    _ = await run(trial)

    assert [message.kind for message in trial.messages] == ["request", "response"]
    assert {(m.run_id, m.conversation_id) for m in trial.messages} == {
        ("run-1", "conversation-1")
    }


@pytest.mark.asyncio
async def test_a_trial_streams_the_thinking_then_the_answer(
    test_inventory: ParsedInventory,
):
    trial = Trial(
        resolution(test_inventory, "free-text", "qwen3-8b-awq@fake"),
        CASE,
        transport=FakeTransport(),
    )

    events = await run(trial)

    starts = [e.part for e in events if isinstance(e, PartStartEvent)]
    assert [type(part) for part in starts] == [ThinkingPart, TextPart]

    result = events[-1]
    assert isinstance(result, AgentRunResultEvent)
    assert result.result.output == ANSWER


@pytest.mark.asyncio
async def test_an_empty_system_prompt_sends_no_system_message(
    test_inventory: ParsedInventory,
):
    fake = FakeTransport()
    _ = await run(
        Trial(
            resolution(test_inventory, "baseline", "gpt-oss-20b@fake"),
            CASE,
            transport=fake,
        )
    )

    assert fake.requests[0]["messages"] == [{"role": "user", "content": CASE}]


@pytest.mark.asyncio
async def test_the_fields_pydantic_ai_types_go_out_as_the_request_names_them(
    test_inventory: ParsedInventory,
):
    cell = resolution(test_inventory, "free-text", "qwen3-8b-awq@fake")
    cell = replace(
        cell,
        sampling=Sampling("explicit", {"stop": ["\n\n"], "max_tokens": 64, "top_k": 5}),
    )
    fake = FakeTransport()

    _ = await run(Trial(cell, CASE, transport=fake))

    # pydantic-ai sends `max_tokens` by OpenAI's newer name, which vLLM takes
    # as well
    sent = fake.requests[0]
    assert (sent["stop"], sent["max_completion_tokens"], sent["top_k"]) == (
        ["\n\n"],
        64,
        5,
    )


@pytest.mark.asyncio
async def test_a_credential_goes_out_as_the_api_key(test_inventory: ParsedInventory):
    headers: list[str | None] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        headers.append(request.headers.get("authorization"))
        body: Any = json.loads(request.content)
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(stream(body)).encode(),
        )

    cell = resolution(test_inventory, "free-text", "qwen3-8b-awq@fake")
    _ = await run(
        Trial(cell, CASE, api_key="s3cret", transport=httpx2.MockTransport(handler))
    )

    assert headers == ["Bearer s3cret"]


@pytest.fixture
def fake_endpoint() -> Iterator[str]:
    fake = server("127.0.0.1", 0)
    host, port = fake.server_address[:2]
    thread = threading.Thread(target=fake.serve_forever, daemon=True)
    thread.start()

    yield f"http://{host!s}:{port}/v1/"

    fake.shutdown()
    fake.server_close()


@pytest.mark.asyncio
async def test_a_trial_runs_against_the_fake_over_http(
    test_inventory: ParsedInventory, fake_endpoint: str
):
    cell = resolution(test_inventory, "free-text", "gpt-oss-20b@fake")
    cell = replace(cell, endpoint=fake_endpoint)
    trial = Trial(cell, CASE)

    events = await run(trial)

    result = events[-1]
    assert isinstance(result, AgentRunResultEvent)
    assert result.result.output == ANSWER
    # and what streamed back is kept whole
    [response] = trial.responses
    assert response.startswith(b"data: {")
    assert response.endswith(b"data: [DONE]\n\n")


# ------------------------------------------------------------------ coercion


def answer(events: list[AgentStreamEvent | AgentRunResultEvent[Any]]) -> Any:
    result = events[-1]
    assert isinstance(result, AgentRunResultEvent)
    return result.result.output


@pytest.mark.asyncio
async def test_native_asks_for_the_schema_as_written_and_says_nothing_of_it(
    test_inventory: ParsedInventory,
):
    cell = resolution(test_inventory, "plan", "qwen3-8b-awq@fake")
    assert cell.coercion is not None
    fake = FakeTransport()

    events = await run(Trial(cell, CASE, transport=fake))

    [request] = fake.requests
    written: dict[str, Any] = cell.coercion.schema
    sent: dict[str, Any] = request["response_format"]["json_schema"]["schema"]
    assert request["response_format"]["type"] == "json_schema"
    # the schema with its references inlined, as resolution made it: nothing
    # of pydantic-ai's but a sort of its keywords, and its properties in the
    # order written, the order a constrained decoder emits them in
    assert sent == cell.coercion.sent
    assert "$defs" in written
    assert list(sent["properties"]) == list(written["properties"])
    # and no text of pydantic-ai's reaches the model
    system, user = cell.render(CASE)
    assert request["messages"] == [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    # and the two hold a document to the same
    document = answer(events)
    assert invalid(written, document) is None
    assert invalid(sent, document) is None


@pytest.mark.asyncio
async def test_tool_mode_offers_the_schema_as_a_tool_the_answer_is_given_through(
    test_inventory: ParsedInventory,
):
    cell = resolution(test_inventory, "diagnoses-tool", "qwen3-8b-awq@fake")
    assert cell.coercion is not None
    fake = FakeTransport()

    events = await run(Trial(cell, CASE, transport=fake))

    [request] = fake.requests
    [tool] = request["tools"]
    assert tool["function"]["name"] == "final_result"
    # said to be what the coercion says it is, not in pydantic-ai's words
    assert tool["function"]["description"] == cell.coercion.tool_description
    assert tool["function"]["parameters"] == cell.coercion.sent
    assert "response_format" not in request

    assert invalid(cell.coercion.schema, answer(events)) is None


@pytest.mark.asyncio
async def test_prompted_shows_the_schema_and_holds_the_answer_to_nothing(
    test_inventory: ParsedInventory,
):
    cell = resolution(
        test_inventory, "challenge-coercion-prompted", "qwen3-8b-awq@fake"
    )
    assert cell.coercion is not None
    fake = FakeTransport()

    events = await run(Trial(cell, CASE, transport=fake))

    [request] = fake.requests
    # no JSON mode either: prompted is the schema shown and nothing more
    assert "response_format" not in request
    assert "tools" not in request
    assert cell.slots["schema_prompt"] in request["messages"][0]["content"]

    assert invalid(cell.coercion.schema, answer(events)) is None


@pytest.mark.asyncio
async def test_an_answer_that_doesn_t_parse_is_not_asked_for_again(
    test_inventory: ParsedInventory,
):
    bodies: list[Any] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        # prose where the schema wants a document
        text = "".join(stream({"model": "Qwen/Qwen3-8B-AWQ", "messages": []}))
        return httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, content=text.encode()
        )

    cell = resolution(
        test_inventory, "challenge-coercion-prompted", "qwen3-8b-awq@fake"
    )

    with pytest.raises(UnexpectedModelBehavior):
        _ = await run(Trial(cell, CASE, transport=httpx2.MockTransport(handler)))

    assert len(bodies) == 1


@pytest.mark.asyncio
async def test_a_seed_is_the_trial_s_and_goes_out_with_it(
    test_inventory: ParsedInventory,
):
    fake = FakeTransport()

    _ = await run(
        Trial(
            resolution(test_inventory, "free-text", "qwen3-8b-awq@fake"),
            CASE,
            transport=fake,
            seed=42,
        )
    )

    assert fake.requests[0]["seed"] == 42


# ------------------------------------------------------------------- toolset


def entry_points(inventory: ParsedInventory) -> dict[str, str]:
    """What each of the inventory's tools runs, by the tool's name."""
    return {
        trail.name: details.implementation.entry_point
        for trail, details in inventory.tool.values()
        if details.implementation is not None
    }


def returned(request: dict[str, Any]) -> list[str]:
    """What the tools returned, as a request sends it back."""
    return [m["content"] for m in request["messages"] if m["role"] == "tool"]


@pytest.mark.asyncio
async def test_a_trial_offers_the_tools_as_resolution_wrote_them(
    test_inventory: ParsedInventory,
):
    cell = resolution(test_inventory, "test-tools", "qwen3-8b-awq@fake")
    fake = FakeTransport()

    _ = await run(
        Trial(cell, CASE, transport=fake, implementations=entry_points(test_inventory))
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
        for tool in cell.tools
    ]
    # in the order written, keywords and all
    assert [json.dumps(o["function"]["parameters"]) for o in offered] == [
        json.dumps(tool.parameters) for tool in cell.tools
    ]


@pytest.mark.asyncio
async def test_each_call_is_run_and_what_it_returned_goes_back(
    test_inventory: ParsedInventory,
):
    cell = resolution(test_inventory, "test-tools", "qwen3-8b-awq@fake")
    fake = FakeTransport()
    trial = Trial(
        cell, CASE, transport=fake, implementations=entry_points(test_inventory)
    )

    events = await run(trial)

    # a round for each tool, then the answer
    assert len(fake.requests) == 3
    assert returned(fake.requests[-1]) == ["asdf", "0"]
    assert answer(events) == ANSWER
    # and every body is kept as it was sent
    assert [json.loads(body) for body in trial.requests] == fake.requests


def broken() -> str:
    raise RuntimeError("the index is down")


@pytest.mark.asyncio
async def test_a_tool_that_fails_tells_the_model_why(test_inventory: ParsedInventory):
    cell = resolution(test_inventory, "test-tools", "qwen3-8b-awq@fake")
    implementations = entry_points(test_inventory) | {
        "sentinel_string": f"{__name__}:broken"
    }
    fake = FakeTransport()

    events = await run(
        Trial(cell, CASE, transport=fake, implementations=implementations)
    )

    assert returned(fake.requests[-1]) == ["RuntimeError: the index is down", "0"]
    # and the trial carries on
    assert answer(events) == ANSWER


@pytest.mark.asyncio
async def test_a_model_still_calling_after_its_rounds_is_stopped(
    test_inventory: ParsedInventory,
):
    bodies: list[Any] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        bodies.append(body)
        # as if nothing had been called yet: the fake calls on and on
        text = "".join(stream(body | {"messages": body["messages"][:1]}))
        return httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, content=text.encode()
        )

    cell = resolution(test_inventory, "test-tools", "qwen3-8b-awq@fake")
    trial = Trial(
        cell,
        CASE,
        transport=httpx2.MockTransport(handler),
        implementations=entry_points(test_inventory),
    )

    with pytest.raises(UsageLimitExceeded):
        _ = await run(trial)

    # its rounds, and the one it was to answer in
    assert len(bodies) == TOOL_ROUNDS + 1
    # and the messages as far as it got: the last round's results, unsent
    assert len(trial.messages) == 2 * (TOOL_ROUNDS + 1) + 1
    assert trial.messages[-1].kind == "request"


def test_a_tool_with_nothing_to_run_is_refused_before_anything_is_sent(
    test_inventory: ParsedInventory,
):
    cell = resolution(test_inventory, "test-tools", "qwen3-8b-awq@fake")

    with pytest.raises(ValueError, match="'sentinel_op' has nothing to run"):
        _ = Trial(
            cell,
            CASE,
            transport=FakeTransport(),
            implementations={
                "sentinel_string": "chatddx.runtime.tools:sentinel_string"
            },
        )


def test_an_answer_that_doesn_t_hold_says_where():
    schema: dict[str, JsonValue] = {"type": "object", "required": ["urgent"]}

    assert invalid(schema, {"urgent": True}) is None
    assert invalid(schema, {}) == "$: 'urgent' is a required property"

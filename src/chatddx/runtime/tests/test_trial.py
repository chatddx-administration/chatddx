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
)

from chatddx.core import settings
from chatddx.dx.fake_vllm import ANSWER, FakeTransport, server, stream
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.parsers.inventory import parse
from chatddx.runtime.resolution import Resolution, Sampling, resolve
from chatddx.runtime.trial import Trial, invalid

CASE = "A patient presents with a cough."


@pytest.fixture(scope="module")
def inventory() -> ParsedInventory:
    return parse(settings.INVENTORY_PATH / "inventory.toml")


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
async def test_a_trial_sends_what_resolution_wrote(inventory: ParsedInventory):
    cell = resolution(inventory, "free-text", "qwen3-8b-awq@fake")
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
    assert trial.request is not None
    assert json.loads(trial.request) == fake.requests[0]


@pytest.mark.asyncio
async def test_a_trial_streams_the_thinking_then_the_answer(inventory: ParsedInventory):
    trial = Trial(
        resolution(inventory, "free-text", "qwen3-8b-awq@fake"),
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
    inventory: ParsedInventory,
):
    fake = FakeTransport()
    _ = await run(
        Trial(
            resolution(inventory, "baseline", "gpt-oss-20b@fake"), CASE, transport=fake
        )
    )

    assert fake.requests[0]["messages"] == [{"role": "user", "content": CASE}]


@pytest.mark.asyncio
async def test_the_fields_pydantic_ai_types_go_out_as_the_request_names_them(
    inventory: ParsedInventory,
):
    cell = resolution(inventory, "free-text", "qwen3-8b-awq@fake")
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
async def test_a_credential_goes_out_as_the_api_key(inventory: ParsedInventory):
    headers: list[str | None] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        headers.append(request.headers.get("authorization"))
        body: Any = json.loads(request.content)
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(stream(body)).encode(),
        )

    cell = resolution(inventory, "free-text", "qwen3-8b-awq@fake")
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
    inventory: ParsedInventory, fake_endpoint: str
):
    cell = resolution(inventory, "free-text", "gpt-oss-20b@fake")
    cell = replace(cell, endpoint=fake_endpoint)

    events = await run(Trial(cell, CASE))

    result = events[-1]
    assert isinstance(result, AgentRunResultEvent)
    assert result.result.output == ANSWER


# ------------------------------------------------------------------ coercion


def answer(events: list[AgentStreamEvent | AgentRunResultEvent[Any]]) -> Any:
    result = events[-1]
    assert isinstance(result, AgentRunResultEvent)
    return result.result.output


@pytest.mark.asyncio
async def test_native_asks_for_the_schema_as_written_and_says_nothing_of_it(
    inventory: ParsedInventory,
):
    cell = resolution(inventory, "plan", "qwen3-8b-awq@fake")
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
    inventory: ParsedInventory,
):
    cell = resolution(inventory, "diagnoses-tool", "qwen3-8b-awq@fake")
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
    inventory: ParsedInventory,
):
    cell = resolution(inventory, "challenge-coercion-prompted", "qwen3-8b-awq@fake")
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
    inventory: ParsedInventory,
):
    bodies: list[Any] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        # prose where the schema wants a document
        text = "".join(stream({"model": "Qwen/Qwen3-8B-AWQ", "messages": []}))
        return httpx2.Response(
            200, headers={"content-type": "text/event-stream"}, content=text.encode()
        )

    cell = resolution(inventory, "challenge-coercion-prompted", "qwen3-8b-awq@fake")

    with pytest.raises(UnexpectedModelBehavior):
        _ = await run(Trial(cell, CASE, transport=httpx2.MockTransport(handler)))

    assert len(bodies) == 1


@pytest.mark.asyncio
async def test_a_seed_is_the_trial_s_and_goes_out_with_it(inventory: ParsedInventory):
    fake = FakeTransport()

    _ = await run(
        Trial(
            resolution(inventory, "free-text", "qwen3-8b-awq@fake"),
            CASE,
            transport=fake,
            seed=42,
        )
    )

    assert fake.requests[0]["seed"] == 42


def test_an_answer_that_doesn_t_hold_says_where():
    schema: dict[str, JsonValue] = {"type": "object", "required": ["urgent"]}

    assert invalid(schema, {"urgent": True}) is None
    assert invalid(schema, {}) == "$: 'urgent' is a required property"

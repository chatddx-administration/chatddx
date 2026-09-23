import json
import threading
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import httpx2
import pytest
from pydantic_ai import (
    AgentRunResultEvent,
    AgentStreamEvent,
    PartStartEvent,
    TextPart,
    ThinkingPart,
)

from chatddx.core import settings
from chatddx.dx.fake_vllm import ANSWER, FakeTransport, server, stream
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.parsers.inventory import parse
from chatddx.runtime.resolution import Resolution, Sampling, resolve
from chatddx.runtime.trial import Trial

pytestmark = pytest.mark.asyncio

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


async def run(trial: Trial) -> list[AgentStreamEvent | AgentRunResultEvent[str]]:
    async with trial.stream() as events:
        return [event async for event in events]


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


async def test_a_trial_runs_against_the_fake_over_http(
    inventory: ParsedInventory, fake_endpoint: str
):
    cell = resolution(inventory, "free-text", "gpt-oss-20b@fake")
    cell = replace(cell, endpoint=fake_endpoint)

    events = await run(Trial(cell, CASE))

    result = events[-1]
    assert isinstance(result, AgentRunResultEvent)
    assert result.result.output == ANSWER

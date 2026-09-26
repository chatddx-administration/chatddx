# pyright: basic
import json
from collections.abc import Callable
from typing import Any

import pytest
from django.test import Client

from chatddx.dev.fake_vllm import FakeTransport
from chatddx.django.api import runs

type Events = list[dict[str, Any]]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeTransport:
    """The fake vLLM, which the API's runs are sent to."""
    transport = FakeTransport()
    monkeypatch.setattr(runs, "TRANSPORT", transport)
    return transport


@pytest.fixture
def through(monkeypatch: pytest.MonkeyPatch) -> Callable[[Any], None]:
    """Send the API's runs through `transport`."""

    def through(transport: Any) -> None:
        monkeypatch.setattr(runs, "TRANSPORT", transport)

    return through


@pytest.fixture
def alex(client: Client, django_user_model: Any) -> Client:
    """alex's session, on the test inventory: the archive's is shared with alex."""
    client.force_login(django_user_model.objects.create_user(username="alex"))
    return client


@pytest.fixture
def run(alex: Client, fake: FakeTransport) -> Callable[..., Events]:
    """Run a cell on a case, as alex, and answer with the events it streamed."""

    def run(**spec: Any) -> Events:
        response: Any = alex.post("/api/runs", spec, content_type="application/json")
        assert response.status_code == 200, response.content
        assert response["Content-Type"] == "text/event-stream"
        return events(b"".join(response.streaming_content))

    return run


def events(streamed: bytes) -> Events:
    """What a stream of server-sent events says, each event's name checked."""
    said: Events = []

    for block in streamed.decode().strip().split("\n\n"):
        name, data = block.split("\n")
        event = json.loads(data.removeprefix("data: "))
        assert name == f"event: {kind_of(event)}"
        said.append(event)

    return said


def kind_of(event: dict[str, Any]) -> str:
    """The API's own events by their type, pydantic-ai's by their event_kind."""
    return event.get("type") or event["event_kind"]


def of(events: Events, kind: str) -> Events:
    return [event for event in events if kind_of(event) == kind]


def written(events: Events, part_kind: str) -> str:
    """What the LLM wrote as parts of `part_kind`: thinking, or text."""
    said = ""

    for event in events:
        match event.get("event_kind"):
            case "part_start" if event["part"]["part_kind"] == part_kind:
                said += event["part"]["content"]
            case "part_delta" if event["delta"]["part_delta_kind"] == part_kind:
                said += event["delta"]["content_delta"]

    return said

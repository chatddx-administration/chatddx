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
def alex(
    provision: Callable[..., None], client: Client, django_user_model: Any
) -> Client:
    """alex's session, on the test inventory: the archive's is shared with alex."""
    provision()
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
    """What a stream of server-sent events says, each event's type checked."""
    said: Events = []

    for block in streamed.decode().strip().split("\n\n"):
        kind, data = block.split("\n")
        event = json.loads(data.removeprefix("data: "))
        assert kind == f"event: {event['type']}"
        said.append(event)

    return said


def of(events: Events, kind: str) -> Events:
    return [event for event in events if event["type"] == kind]


def parts(events: Events) -> list[tuple[str, str]]:
    """What the LLM sent back part by part, pieces joined, and what tools returned."""
    said: list[list[str]] = []
    begun: dict[int, list[str]] = {}

    for event in events:
        match event["type"]:
            case "thinking" | "text" | "call":
                if event["part"] not in begun:
                    begun[event["part"]] = [event.get("tool", event["type"]), ""]
                    said.append(begun[event["part"]])

                piece = event["arguments"] if "tool" in event else event["text"]
                begun[event["part"]][1] += piece
            case "result":
                said.append([f"result {event['tool']}", event["content"]])

    return [(kind, text) for kind, text in said]

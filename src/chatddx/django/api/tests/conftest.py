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
def fake(fake: FakeTransport, monkeypatch: pytest.MonkeyPatch) -> FakeTransport:
    monkeypatch.setattr(runs, "TRANSPORT", fake)
    return fake


@pytest.fixture
def through(monkeypatch: pytest.MonkeyPatch) -> Callable[[Any], None]:

    def through(transport: Any) -> None:
        monkeypatch.setattr(runs, "TRANSPORT", transport)

    return through


@pytest.fixture
def alice(client: Client, django_user_model: Any) -> Client:
    client.force_login(django_user_model.objects.create_user(username="alice"))
    return client


@pytest.fixture
def run(alice: Client, fake: FakeTransport) -> Callable[..., Events]:

    def run(**spec: Any) -> Events:
        response: Any = alice.post("/api/runs", spec, content_type="application/json")
        assert response.status_code == 200, response.content
        assert response["Content-Type"] == "text/event-stream"
        return events(b"".join(response.streaming_content))

    return run


def events(streamed: bytes) -> Events:
    said: Events = []

    for block in streamed.decode().strip().split("\n\n"):
        name, data = block.split("\n")
        event = json.loads(data.removeprefix("data: "))
        assert name == f"event: {kind_of(event)}"
        said.append(event)

    return said


def kind_of(event: dict[str, Any]) -> str:
    return event.get("type") or event["event_kind"]


def of(events: Events, kind: str) -> Events:
    return [event for event in events if kind_of(event) == kind]


def written(events: Events, part_kind: str) -> str:
    said = ""

    for event in events:
        match event.get("event_kind"):
            case "part_start" if event["part"]["part_kind"] == part_kind:
                said += event["part"]["content"]
            case "part_delta" if event["delta"]["part_delta_kind"] == part_kind:
                said += event["delta"]["content_delta"]

    return said

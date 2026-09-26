# pyright: basic
"""
Runs stream as they come over WSGI and ASGI alike: the gated fake vLLM holds
its answer back after its first token until the client has seen it, which a
response that waited for the run to end would never let through. The server
is served in the test's transaction, as Django's test client serves it.
"""

import asyncio
import json
import sys
import threading
from collections.abc import Callable, Iterator
from io import BytesIO
from typing import Any, cast, override

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.asgi import get_asgi_application
from django.core.signals import request_finished, request_started
from django.core.wsgi import get_wsgi_application
from django.db import close_old_connections
from django.test import Client

from chatddx.dev.fake_vllm import FakeTransport
from chatddx.django.api.tests.conftest import events, kind_of, of
from chatddx.history.models import RunModel, RunStatus

BATCH = {
    "configuration": "free-text",
    "stack": "qwen3-8b-awq@fake",
    "tags": ["tag-2"],
}


pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("held_open")]

# a CSRF secret, sent as the cookie and the header alike
TOKEN = "t" * 32


class Gated(FakeTransport):
    def __init__(self) -> None:
        super().__init__()
        self.opened: threading.Event = threading.Event()

    def open(self) -> None:
        self.opened.set()

    @override
    async def next_token(self, generated: int, /) -> None:
        if generated and not await asyncio.to_thread(self.opened.wait, 10):
            raise TimeoutError("nothing was streamed before the run ended")


@pytest.fixture
def gated(through: Callable[[Any], None]) -> Gated:
    transport = Gated()
    through(transport)
    return transport


@pytest.fixture
def held_open() -> Iterator[None]:
    """The test's connection, kept open across requests as the test client keeps it."""
    request_started.disconnect(close_old_connections)
    request_finished.disconnect(close_old_connections)
    yield
    request_started.connect(close_old_connections)
    request_finished.connect(close_old_connections)


@pytest.fixture
def cookie(django_user_model: Any) -> str:
    """alex's session, and a CSRF token beside it."""
    client = Client()
    client.force_login(django_user_model.objects.create_user(username="alex"))
    session = client.cookies[settings.SESSION_COOKIE_NAME].value
    return f"{settings.SESSION_COOKIE_NAME}={session}; csrftoken={TOKEN}"


def asgi(
    request: dict[str, Any], received: Callable[[bytes], bool], cookie: str
) -> list[dict[str, Any]]:
    """Serve `request` as alex; the client goes away once `received` says so."""
    body = json.dumps(request["body"]).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": request["method"],
        "scheme": "http",
        "path": request["path"],
        "raw_path": request["path"].encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"cookie", cookie.encode()),
            (b"x-csrftoken", TOKEN.encode()),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    sent: list[dict[str, Any]] = []

    async def serve() -> None:
        gone = asyncio.Event()
        messages = [{"type": "http.request", "body": body, "more_body": False}]

        async def receive() -> dict[str, Any]:
            if messages:
                return messages.pop(0)

            await gone.wait()
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

            if message["type"] == "http.response.body" and received(
                message.get("body", b"")
            ):
                gone.set()

        await get_asgi_application()(scope, receive, send)

    async_to_sync(serve)()

    return sent


def wsgi(
    request: dict[str, Any], received: Callable[[bytes], bool], cookie: str
) -> bytes:
    """Serve `request` as alex; the client goes away once `received` says so."""
    body = json.dumps(request["body"]).encode()
    environ = {
        "REQUEST_METHOD": request["method"],
        "PATH_INFO": request["path"],
        "SCRIPT_NAME": "",
        "QUERY_STRING": "",
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "HTTP_COOKIE": cookie,
        "HTTP_X_CSRFTOKEN": TOKEN,
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": BytesIO(body),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }
    served = get_wsgi_application()(environ, lambda status, headers: None)
    streamed = b""

    try:
        for chunk in served:
            streamed += chunk

            if received(chunk):
                break
    finally:
        cast(Any, served).close()

    return streamed


def body_of(sent: list[dict[str, Any]]) -> bytes:
    return b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )


def test_a_batch_streams_over_wsgi_case_by_case(gated: Gated, cookie: str):
    def received(chunk: bytes) -> bool:
        if b"event: part_start" in chunk:
            gated.open()
        return False

    said = events(
        wsgi({"method": "POST", "path": "/api/batch", "body": BATCH}, received, cookie)
    )

    assert [kind_of(event) for event in said if kind_of(event) in ("batch", "run")] == [
        "batch",
        "run",
        "run",
    ]
    assert said[-1]["type"] == "summary"
    assert said[-1]["runs"] == 2
    assert RunModel.objects.filter(status=RunStatus.COMPLETED).count() == 2


def test_a_client_that_goes_away_over_wsgi_stops_the_batch(gated: Gated, cookie: str):
    streamed = wsgi(
        {"method": "POST", "path": "/api/batch", "body": BATCH},
        lambda chunk: b"event: part_start" in chunk,
        cookie,
    )
    gated.open()

    [run] = RunModel.objects.all()

    assert b"event: summary" not in streamed
    assert (run.status, run.error) == (RunStatus.ERRORED, "stopped")
    assert len(gated.requests) == 1
    assert gated.aborted == gated.requests
    assert run.requests and run.responses[0].startswith("data: ")
    assert run.conversation is not None
    assert [message.kind for message in run.conversation.messages.all()][-1] == "error"


def test_a_client_that_goes_away_over_asgi_stops_the_batch(gated: Gated, cookie: str):
    sent = asgi(
        {"method": "POST", "path": "/api/batch", "body": BATCH},
        lambda body: b"event: part_start" in body,
        cookie,
    )
    gated.open()

    [run] = RunModel.objects.all()

    assert b"event: summary" not in body_of(sent)
    assert (run.status, run.error) == (RunStatus.ERRORED, "stopped")
    assert len(gated.requests) == 1
    assert gated.aborted == gated.requests


def test_a_batch_streams_over_asgi_case_by_case(gated: Gated, cookie: str):
    def received(body: bytes) -> bool:
        if b"event: part_start" in body:
            gated.open()
        return False

    said = events(
        body_of(
            asgi(
                {"method": "POST", "path": "/api/batch", "body": BATCH},
                received,
                cookie,
            )
        )
    )

    assert [event["case"] for event in of(said, "run")] == ["case-1", "case-2"]
    assert said[-1]["type"] == "summary"
    assert [row["scorer"] for row in said[-1]["scorers"]] == [
        "first_mention",
        "reciprocal_rank",
    ]

"""
The fake vLLM: a chat completions server that stands in for vLLM, so a cell
can be tried end to end without a GPU. `chatddx fake-vllm` serves it, and
the inventory's `@fake` stacks send to it.

It streams as vLLM does, the reasoning parser's output in `reasoning` and the
answer in `content`, and it takes the request as the model's chat template
would: Qwen3 thinks unless `enable_thinking` is false, and gpt-oss always
does. What it thinks about is the request it was sent, field by field, and
it answers every case alike, since nothing in it reads the case. Like a
model, it spends `max_tokens` on thinking first. A word is a token.
"""

import json
import re
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Annotated, Any, override

import httpx2
import typer

ANSWER = "Fake diagnosis A\nFake diagnosis B\nFake diagnosis C"

# what a request says beside the fields its thinking reads back
_TRANSPORT = frozenset({"messages", "model", "stream", "stream_options"})

_WORD = re.compile(r"\S+\s*|\s+")


def thinking(body: dict[str, Any]) -> str | None:
    """What the model thinks, if it thinks: the request it was sent."""
    model = str(body.get("model", "")).lower()
    kwargs: dict[str, Any] = body.get("chat_template_kwargs") or {}

    if "qwen3" in model:
        if kwargs.get("enable_thinking") is False:
            return None
    elif "gpt-oss" not in model:
        return None

    messages = [
        f"{m.get('role')} ({len(str(m.get('content') or '').split())} words)"
        for m in body.get("messages", [])
    ]
    fields = [f"{k}={json.dumps(v)}" for k, v in body.items() if k not in _TRANSPORT]

    return (
        "I am the fake vLLM, and nothing here reads the case. "
        + f"I was sent {', '.join(messages) or 'no messages'}, "
        + f"and {' '.join(fields) or 'no other fields'}. "
        + "So I answer as I always do."
    )


def respond(body: dict[str, Any]) -> tuple[str | None, str, str]:
    """The thinking, the answer and the finish reason, within `max_tokens`."""
    thought_text = thinking(body)
    thought = _words(thought_text or "")
    answer = _words(ANSWER)

    budget = body.get("thinking_token_budget")
    if isinstance(budget, int):
        thought = thought[:budget]

    finish = "stop"
    # as vLLM does: OpenAI's newer name first
    limit = body.get("max_completion_tokens", body.get("max_tokens"))

    if isinstance(limit, int) and len(thought) + len(answer) > limit:
        finish = "length"
        thought = thought[:limit]
        answer = answer[: limit - len(thought)]

    reasoning = "".join(thought) if thought_text is not None else None

    return reasoning, "".join(answer), finish


def completion(body: dict[str, Any]) -> dict[str, Any]:
    """The whole response, for a request that doesn't stream."""
    reasoning, answer, finish = respond(body)
    message: dict[str, Any] = {"role": "assistant", "content": answer}

    if reasoning is not None:
        message["reasoning"] = reasoning

    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model"),
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": _usage(body, reasoning, answer),
    }


def stream(body: dict[str, Any]) -> Iterator[str]:
    """The response as server-sent events, a word at a time."""
    reasoning, answer, finish = respond(body)
    model = body.get("model")

    yield _event(model, {"role": "assistant", "content": ""})

    for word in _words(reasoning or ""):
        yield _event(model, {"reasoning": word})

    for word in _words(answer):
        yield _event(model, {"content": word})

    yield _event(model, {}, finish)

    options: dict[str, Any] = body.get("stream_options") or {}

    if options.get("include_usage"):
        yield _data(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [],
                "usage": _usage(body, reasoning, answer),
            }
        )

    yield "data: [DONE]\n\n"


class FakeTransport(httpx2.AsyncBaseTransport):
    """The fake vLLM in-process, keeping every request it was sent."""

    def __init__(self):
        self.requests: list[dict[str, Any]] = []

    @override
    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append(body)

        if body.get("stream"):
            return httpx2.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content="".join(stream(body)).encode(),
            )

        return httpx2.Response(200, json=completion(body))


class _Handler(BaseHTTPRequestHandler):
    # seconds between the streamed words
    delay: float = 0.0

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/v1/chat/completions":
            self._json(404, {"error": {"message": f"no route for {self.path}"}})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except ValueError as e:
            self._json(400, {"error": {"message": str(e)}})
            return

        if not body.get("stream"):
            self._json(200, completion(body))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        for event in stream(body):
            _ = self.wfile.write(event.encode())
            self.wfile.flush()
            time.sleep(self.delay)

    def _json(self, status: int, body: dict[str, Any]) -> None:
        content = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        _ = self.wfile.write(content)


def server(host: str, port: int, delay: float = 0.0) -> ThreadingHTTPServer:
    handler = type("Handler", (_Handler,), {"delay": delay})
    return ThreadingHTTPServer((host, port), handler)


def fake_vllm(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 12099,
    delay: Annotated[
        float, typer.Option(help="seconds between the streamed words")
    ] = 0.03,
):
    """Serve the fake vLLM the inventory's @fake stacks send to."""
    fake = server(host, port, delay)
    typer.echo(f"the fake vLLM, at http://{host}:{port}/v1/")

    try:
        fake.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        fake.server_close()


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def _event(model: Any, delta: dict[str, Any], finish: str | None = None) -> str:
    return _data(
        {
            "id": "chatcmpl-fake",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
    )


def _data(chunk: dict[str, Any]) -> str:
    return f"data: {json.dumps(chunk)}\n\n"


def _usage(body: dict[str, Any], reasoning: str | None, answer: str) -> dict[str, int]:
    prompt = sum(
        len(str(m.get("content") or "").split()) for m in body.get("messages", [])
    )
    completion_tokens = len((reasoning or "").split()) + len(answer.split())

    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt + completion_tokens,
    }

import json
import re
import select
import socket
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Annotated, Any, cast, override

import httpx2
import typer

ANSWER = "Fake diagnosis A\nFake diagnosis B\nFake diagnosis C"

FINAL_RESULT = "final_result"

# where a runaway ends, with no max_tokens to end it sooner
CONTEXT = 32768

_TRANSPORT = frozenset({"messages", "model", "stream", "stream_options"})

# a word and the space after it; a thinking tag is a token of its own, as it
# is in Qwen3's vocabulary, and vLLM streams it alone
_WORD = re.compile(r"</?think>|(?:(?!</?think>)\S)+\s*|\s+")


def thinking(body: dict[str, Any]) -> str | None:
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
    fields = [_field(k, v) for k, v in body.items() if k not in _TRANSPORT]

    return (
        "I am the fake vLLM, and nothing here reads the case. "
        + f"I was sent {', '.join(messages) or 'no messages'}, "
        + f"and {' '.join(fields) or 'no other fields'}. "
        + "So I answer as I always do."
    )


@dataclass(frozen=True)
class Reply:
    reasoning: str | None
    content: str
    # a call to a tool: its name and its arguments, as JSON
    call: tuple[str, str] | None
    finish: str
    # the newlines it goes on with after its answer, a token each
    runaway: int = 0


def respond(
    body: dict[str, Any], reasoning_parser: bool = True, runaway: bool = False
) -> Reply:
    thought_text = None if _held(body, reasoning_parser) else thinking(body)
    thought = _words(thought_text or "")
    tool = _next_tool(body)
    schema = _schema(body)
    call: tuple[str, str] | None = None

    if tool is not None:
        call = (tool["name"], json.dumps(instance(tool.get("parameters") or {})))
        answer: list[str] = []
    elif schema is not None:
        answer = _words(json.dumps(instance(schema), indent=2))
    else:
        answer = _words(ANSWER)

    budget = body.get("thinking_token_budget")
    if isinstance(budget, int):
        thought = thought[:budget]

    finish = "tool_calls" if call else "stop"
    # as vLLM does: OpenAI's newer name first
    limit = body.get("max_completion_tokens", body.get("max_tokens"))

    if isinstance(limit, int) and len(thought) + len(answer) > limit:
        finish = "length"
        thought = thought[:limit]
        answer = answer[: limit - len(thought)]

    newlines = 0

    if runaway and finish == "stop":
        # as gpt-oss does on malborg at times: the answer ends, the tokens don't
        room = limit if isinstance(limit, int) else CONTEXT - _prompt_tokens(body)
        newlines = max(room - len(thought) - len(answer), 0)
        finish = "length"

    reasoning = "".join(thought) if thought_text is not None else None

    if reasoning is not None and not reasoning_parser:
        # nothing takes the thinking out of the answer
        closed = "\n</think>\n\n" if finish != "length" or answer else ""
        return Reply(
            None,
            f"<think>\n{reasoning}{closed}{''.join(answer)}",
            call,
            finish,
            newlines,
        )

    return Reply(reasoning, "".join(answer), call, finish, newlines)


def completion(
    body: dict[str, Any], reasoning_parser: bool = True, runaway: bool = False
) -> dict[str, Any]:
    reply = respond(body, reasoning_parser, runaway)
    message: dict[str, Any] = {
        "role": "assistant",
        "content": reply.content + "\n" * reply.runaway,
    }

    if reply.reasoning is not None:
        message["reasoning"] = reply.reasoning

    if reply.call is not None:
        name, arguments = reply.call
        message["tool_calls"] = [
            {
                "id": "chatcmpl-tool-fake",
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ]

    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model"),
        "choices": [{"index": 0, "message": message, "finish_reason": reply.finish}],
        "usage": _usage(body, reply),
    }


def stream(
    body: dict[str, Any], reasoning_parser: bool = True, runaway: bool = False
) -> Iterator[str]:
    for event, _ in _stream(body, respond(body, reasoning_parser, runaway)):
        yield event


def _stream(body: dict[str, Any], reply: Reply) -> Iterator[tuple[str, int]]:
    model = body.get("model")
    options: dict[str, Any] = body.get("stream_options") or {}
    usage = bool(options.get("include_usage"))
    continuous = usage and bool(options.get("continuous_usage_stats"))
    prompt = _prompt_tokens(body)
    generated = 0

    def event(delta: dict[str, Any], finish: str | None = None) -> tuple[str, int]:
        so_far = _counted(prompt, generated) if continuous else None
        return _event(model, delta, finish, so_far), generated

    yield event({"role": "assistant", "content": ""})

    for word in _words(reply.reasoning or ""):
        generated += len(word.split())
        yield event({"reasoning": word})

    for word in _words(reply.content):
        generated += len(word.split())
        yield event({"content": word})

    for _ in range(reply.runaway):
        generated += 1
        yield event({"content": "\n"})

    if reply.call is not None:
        name, arguments = reply.call
        yield event(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "chatcmpl-tool-fake",
                        "type": "function",
                        "function": {"name": name, "arguments": ""},
                    }
                ]
            },
        )

        for piece in _words(arguments):
            generated += len(piece.split())
            yield event(
                {"tool_calls": [{"index": 0, "function": {"arguments": piece}}]},
            )

    yield event({}, reply.finish)

    if usage:
        chunk: dict[str, Any] = {
            "id": "chatcmpl-fake",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [],
            "usage": _usage(body, reply),
        }
        yield _data(chunk), generated

    yield "data: [DONE]\n\n", generated


def instance(
    schema: Any,
    root: Any = None,
    key: str = "value",
    n: int | None = None,
    depth: int = 0,
) -> Any:
    root = schema if root is None else root

    if not isinstance(schema, dict) or depth > 12:
        return None

    schema = cast(dict[str, Any], schema)

    if "$ref" in schema:
        return instance(_resolve(root, schema["$ref"]), root, key, n, depth + 1)

    if "const" in schema:
        return schema["const"]

    if schema.get("enum"):
        return schema["enum"][0]

    for union in ("anyOf", "oneOf", "allOf"):
        options = [o for o in schema.get(union, []) if o.get("type") != "null"]
        if options:
            return instance(options[0], root, key, n, depth + 1)

    kind = schema.get("type")

    if isinstance(kind, list):
        kind = next((k for k in cast(list[str], kind) if k != "null"), "null")

    match kind:
        case "object":
            properties: dict[str, Any] = schema.get("properties", {})
            return {
                name: instance(sub, root, name, n, depth + 1)
                for name, sub in properties.items()
            }
        case "array":
            count = min(max(schema.get("minItems", 3), 1), schema.get("maxItems", 3))
            return [
                instance(schema.get("items", {}), root, key, i, depth + 1)
                for i in range(1, count + 1)
            ]
        case "string":
            return f"fake {key.replace('_', ' ')}" + ("" if n is None else f" {n}")
        case "integer":
            return int(schema.get("minimum", n or 1))
        case "number":
            return float(schema.get("minimum", n or 1))
        case "boolean":
            return False
        case _:
            if "properties" in schema:
                return instance(schema | {"type": "object"}, root, key, n, depth + 1)
            return None


class FakeTransport(httpx2.AsyncBaseTransport):
    def __init__(self, reasoning_parser: bool = True, runaway: bool = False):
        self.requests: list[dict[str, Any]] = []
        self.aborted: list[dict[str, Any]] = []
        self.reasoning_parser: bool = reasoning_parser
        self.runaway: bool = runaway

    @override
    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append(body)

        if body.get("stream"):
            return httpx2.Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=_Streamed(self, body),
            )

        return httpx2.Response(
            200,
            json=completion(body, self.reasoning_parser, self.runs_away(body)),
        )

    def runs_away(self, _body: dict[str, Any], /) -> bool:
        return self.runaway

    async def next_token(self, _generated: int, /) -> None:
        pass


class _Streamed(httpx2.AsyncByteStream):
    def __init__(self, fake: FakeTransport, body: dict[str, Any]):
        self._fake: FakeTransport = fake
        self._body: dict[str, Any] = body
        self._ended: bool = False

    @override
    async def __aiter__(self) -> AsyncIterator[bytes]:
        fake = self._fake
        reply = respond(self._body, fake.reasoning_parser, fake.runs_away(self._body))
        # one ahead, to know the last as it goes: a runaway is too long to list
        events = enumerate(_stream(self._body, reply))
        ahead = next(events, None)
        sent = 0

        while ahead is not None:
            i, (event, generated) = ahead

            if i:
                await fake.next_token(sent)

            ahead = next(events, None)
            self._ended = ahead is None
            yield event.encode()
            sent = generated

    @override
    async def aclose(self) -> None:
        if not self._ended:
            self._ended = True
            self._fake.aborted.append(self._body)


class _Handler(BaseHTTPRequestHandler):
    delay: float = 0.0
    reasoning_parser: bool = True
    runaway: bool = False

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
            self._json(200, completion(body, self.reasoning_parser, self.runaway))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        reply = respond(body, self.reasoning_parser, self.runaway)
        sent = 0

        for i, (event, generated) in enumerate(_stream(body, reply)):
            if (i and not self._next_token()) or not self._sent(event.encode()):
                whole = _usage(body, reply)["completion_tokens"]
                self.log_message(
                    "aborted: the client hung up after %d of %d tokens", sent, whole
                )
                return

            sent = generated

    def _next_token(self) -> bool:
        ready, _, _ = select.select([self.connection], [], [], self.delay)

        if not ready:
            return True

        try:
            return self.connection.recv(1, socket.MSG_PEEK) != b""
        except OSError:
            return False

    def _sent(self, data: bytes) -> bool:
        try:
            _ = self.wfile.write(data)
            self.wfile.flush()
        except OSError:
            return False

        return True

    def _json(self, status: int, body: dict[str, Any]) -> None:
        content = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        _ = self.wfile.write(content)


def server(
    host: str,
    port: int,
    delay: float = 0.0,
    reasoning_parser: bool = True,
    runaway: bool = False,
) -> ThreadingHTTPServer:
    handler = type(
        "Handler",
        (_Handler,),
        {"delay": delay, "reasoning_parser": reasoning_parser, "runaway": runaway},
    )
    return ThreadingHTTPServer((host, port), handler)


def fake_vllm(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 12099,
    delay: Annotated[
        float, typer.Option(help="seconds between the streamed words")
    ] = 0.03,
    reasoning_parser: Annotated[
        bool,
        typer.Option(
            help="take the thinking out of the answer, as vLLM's reasoning parser "
            + "does; pelle serves without one"
        ),
    ] = True,
    runaway: Annotated[
        bool,
        typer.Option(
            help="after each answer, go on with newlines till max_tokens or the "
            + "context runs out, as gpt-oss does on malborg at times"
        ),
    ] = False,
):
    fake = server(host, port, delay, reasoning_parser, runaway)
    without = "" if reasoning_parser else ", without a reasoning parser"
    running = ", running away after each answer" if runaway else ""
    typer.echo(f"the fake vLLM, at http://{host}:{port}/v1/{without}{running}")

    try:
        fake.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        fake.server_close()


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


def _event(
    model: Any,
    delta: dict[str, Any],
    finish: str | None = None,
    usage: dict[str, int] | None = None,
) -> str:
    chunk: dict[str, Any] = {
        "id": "chatcmpl-fake",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }

    if usage is not None:
        chunk["usage"] = usage

    return _data(chunk)


def _data(chunk: dict[str, Any]) -> str:
    return f"data: {json.dumps(chunk)}\n\n"


def _usage(body: dict[str, Any], reply: Reply) -> dict[str, int]:
    arguments = reply.call[1] if reply.call else ""
    completion_tokens = sum(
        len(text.split()) for text in (reply.reasoning or "", reply.content, arguments)
    )

    return _counted(_prompt_tokens(body), completion_tokens + reply.runaway)


def _prompt_tokens(body: dict[str, Any]) -> int:
    return sum(
        len(str(m.get("content") or "").split()) for m in body.get("messages", [])
    )


def _counted(prompt: int, completion: int) -> dict[str, int]:
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }


def _held(body: dict[str, Any], reasoning_parser: bool) -> bool:
    response_format: dict[str, Any] = body.get("response_format") or {}
    grammar = response_format.get("type") in ("json_schema", "json_object")

    return not reasoning_parser and (grammar or body.get("tool_choice") == "required")


def _next_tool(body: dict[str, Any]) -> dict[str, Any] | None:
    messages: list[dict[str, Any]] = body.get("messages", [])
    called: set[str] = {
        call["function"]["name"]
        for message in messages
        if message.get("role") == "assistant"
        for call in cast(list[dict[str, Any]], message.get("tool_calls") or [])
    }
    offered: list[dict[str, Any]] = [
        tool["function"] for tool in cast(list[dict[str, Any]], body.get("tools") or [])
    ]
    pending = [
        tool
        for tool in offered
        if tool["name"] not in called and tool["name"] != FINAL_RESULT
    ]

    if pending:
        return pending[0]

    return next((tool for tool in offered if tool["name"] == FINAL_RESULT), None)


def _schema(body: dict[str, Any]) -> dict[str, Any] | None:
    response_format: dict[str, Any] = body.get("response_format") or {}

    if response_format.get("type") == "json_schema":
        return response_format["json_schema"].get("schema") or {}

    if response_format.get("type") == "json_object":
        return {"type": "object"}

    for message in body.get("messages", []):
        if message.get("role") == "system":
            shown = _shown(str(message.get("content") or ""))
            if shown is not None:
                return shown

    return None


def _shown(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()

    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text, match.start())
        except ValueError:
            continue

        if isinstance(value, dict):
            schema = cast(dict[str, Any], value)
            if {"type", "properties"} & schema.keys():
                return schema

    return None


def _resolve(root: Any, ref: str) -> Any:
    node: Any = root

    for part in ref.removeprefix("#/").split("/"):
        node = cast(dict[str, Any], node).get(part) if isinstance(node, dict) else None

    return node


def _field(key: str, value: Any) -> str:
    match key:
        case "response_format":
            return f"response_format={value.get('type')}"
        case "tools":
            return "tools=" + ",".join(tool["function"]["name"] for tool in value)
        case _:
            return f"{key}={json.dumps(value)}"

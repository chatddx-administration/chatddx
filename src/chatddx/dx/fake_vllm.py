"""
The fake vLLM: a chat completions server that stands in for vLLM, so a cell
can be tried end to end without a GPU. `chatddx fake-vllm` serves it, and
the inventory's `@fake` stacks send to it.

It streams as vLLM does, the reasoning parser's output in `reasoning` and the
answer in `content`, and it takes the request as the LLM's chat template
would: Qwen3 thinks unless `enable_thinking` is false, and gpt-oss always
does. What it thinks about is the request it was sent, field by field, and
it answers every case alike, since nothing in it reads the case. Like an
LLM, it spends `max_tokens` on thinking first. A word is a token.

Asked for a structured answer, it gives a document that holds to the
schema: one `response_format` names, as guided decoding would force, or one
a system message shows, as an LLM that follows it would. Offered tools, it
calls each of them once, then answers: through the final-result tool, when
it is offered one.

Without a reasoning parser (`--no-reasoning-parser`), it serves as pelle
does: the thinking stays in `content`, between `<think>` tags, and a grammar
(`response_format`, or `tool_choice` = required) holds the answer from its
first token, so under one it doesn't think at all.
"""

import json
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Annotated, Any, cast, override

import httpx2
import typer

ANSWER = "Fake diagnosis A\nFake diagnosis B\nFake diagnosis C"

# the tool an answer is given through, in tool mode: the trial's, named here
# so the fake stands on its own
FINAL_RESULT = "final_result"

# what a request says beside the fields its thinking reads back
_TRANSPORT = frozenset({"messages", "model", "stream", "stream_options"})

# a word and the space after it; a thinking tag is a token of its own, as it
# is in Qwen3's vocabulary, and vLLM streams it alone
_WORD = re.compile(r"</?think>|(?:(?!</?think>)\S)+\s*|\s+")


def thinking(body: dict[str, Any]) -> str | None:
    """What the LLM thinks, if it thinks: the request it was sent."""
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


def respond(body: dict[str, Any], reasoning_parser: bool = True) -> Reply:
    """What the LLM gives back, within `max_tokens`."""
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

    reasoning = "".join(thought) if thought_text is not None else None

    if reasoning is not None and not reasoning_parser:
        # nothing takes the thinking out of the answer
        closed = "\n</think>\n\n" if finish != "length" or answer else ""
        return Reply(
            None, f"<think>\n{reasoning}{closed}{''.join(answer)}", call, finish
        )

    return Reply(reasoning, "".join(answer), call, finish)


def completion(body: dict[str, Any], reasoning_parser: bool = True) -> dict[str, Any]:
    """The whole response, for a request that doesn't stream."""
    reply = respond(body, reasoning_parser)
    message: dict[str, Any] = {"role": "assistant", "content": reply.content}

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


def stream(body: dict[str, Any], reasoning_parser: bool = True) -> Iterator[str]:
    """The response as server-sent events, a word at a time."""
    reply = respond(body, reasoning_parser)
    model = body.get("model")

    yield _event(model, {"role": "assistant", "content": ""})

    for word in _words(reply.reasoning or ""):
        yield _event(model, {"reasoning": word})

    for word in _words(reply.content):
        yield _event(model, {"content": word})

    if reply.call is not None:
        name, arguments = reply.call
        yield _event(
            model,
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
            yield _event(
                model,
                {"tool_calls": [{"index": 0, "function": {"arguments": piece}}]},
            )

    yield _event(model, {}, reply.finish)

    options: dict[str, Any] = body.get("stream_options") or {}

    if options.get("include_usage"):
        yield _data(
            {
                "id": "chatcmpl-fake",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [],
                "usage": _usage(body, reply),
            }
        )

    yield "data: [DONE]\n\n"


def instance(
    schema: Any,
    root: Any = None,
    key: str = "value",
    n: int | None = None,
    depth: int = 0,
) -> Any:
    """
    A document that holds to `schema`. Strings say what they are, by the
    property that holds them, and count up through an array, as numbers do
    from 1: `fake diagnosis 1`, `fake diagnosis 2`.
    """
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
    """The fake vLLM in-process, keeping every request it was sent."""

    def __init__(self, reasoning_parser: bool = True):
        self.requests: list[dict[str, Any]] = []
        self.reasoning_parser: bool = reasoning_parser

    @override
    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append(body)

        if body.get("stream"):
            return httpx2.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content="".join(stream(body, self.reasoning_parser)).encode(),
            )

        return httpx2.Response(200, json=completion(body, self.reasoning_parser))


class _Handler(BaseHTTPRequestHandler):
    # seconds between the streamed words
    delay: float = 0.0
    reasoning_parser: bool = True

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
            self._json(200, completion(body, self.reasoning_parser))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        for event in stream(body, self.reasoning_parser):
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


def server(
    host: str, port: int, delay: float = 0.0, reasoning_parser: bool = True
) -> ThreadingHTTPServer:
    handler = type(
        "Handler", (_Handler,), {"delay": delay, "reasoning_parser": reasoning_parser}
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
):
    """Serve the fake vLLM the inventory's @fake stacks send to."""
    fake = server(host, port, delay, reasoning_parser)
    without = "" if reasoning_parser else ", without a reasoning parser"
    typer.echo(f"the fake vLLM, at http://{host}:{port}/v1/{without}")

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


def _usage(body: dict[str, Any], reply: Reply) -> dict[str, int]:
    prompt = sum(
        len(str(m.get("content") or "").split()) for m in body.get("messages", [])
    )
    arguments = reply.call[1] if reply.call else ""
    completion_tokens = sum(
        len(text.split()) for text in (reply.reasoning or "", reply.content, arguments)
    )

    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt + completion_tokens,
    }


def _held(body: dict[str, Any], reasoning_parser: bool) -> bool:
    """
    Whether a grammar holds the answer from its first token: without a
    reasoning parser to find where the thinking ends, vLLM holds all of it.
    """
    response_format: dict[str, Any] = body.get("response_format") or {}
    grammar = response_format.get("type") in ("json_schema", "json_object")

    return not reasoning_parser and (grammar or body.get("tool_choice") == "required")


def _next_tool(body: dict[str, Any]) -> dict[str, Any] | None:
    """The first tool offered and not called yet, and the answer's last."""
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
    """The schema an answer is held to, or shown, if any."""
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
    """The first JSON schema written into `text`."""
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
    """A request field as the thinking reads it back, big ones by what they are."""
    match key:
        case "response_format":
            return f"response_format={value.get('type')}"
        case "tools":
            return "tools=" + ",".join(tool["function"]["name"] for tool in value)
        case _:
            return f"{key}={json.dumps(value)}"

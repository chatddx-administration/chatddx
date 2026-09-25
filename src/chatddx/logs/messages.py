"""
A run's exchange as inspect keeps one: pydantic-ai's messages as inspect's
chat messages, and each body sent or received as JSON, a streamed response
as the chunks it came in.
"""

import json
from collections.abc import Iterable, Sequence
from typing import Any, cast

from inspect_ai.model import (
    ChatCompletionChoice,
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    Content,
    ContentReasoning,
    ContentText,
    GenerateConfig,
    ModelOutput,
    ModelUsage,
    StopReason,
)
from inspect_ai.tool import ToolCall, ToolCallError
from pydantic import JsonValue
from pydantic_ai import (
    ModelMessage,
    ModelRequestPart,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

STOP_REASONS: dict[str, StopReason] = {
    "stop": "stop",
    "length": "max_tokens",
    "content_filter": "content_filter",
    "tool_call": "tool_calls",
}

# what a request body's fields are to inspect, those it has a place for
GENERATE_CONFIG: dict[str, str] = {
    "temperature": "temperature",
    "top_p": "top_p",
    "top_k": "top_k",
    "max_tokens": "max_tokens",
    "max_completion_tokens": "max_tokens",
    "presence_penalty": "presence_penalty",
    "frequency_penalty": "frequency_penalty",
    "stop": "stop_seqs",
    "seed": "seed",
    "reasoning_effort": "reasoning_effort",
}

# what a request body carries that isn't a setting
NOT_SETTINGS = frozenset(
    {
        "messages",
        "model",
        "stream",
        "stream_options",
        "response_format",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
    }
)


def chat_messages(messages: Sequence[ModelMessage]) -> list[ChatMessage]:
    """
    The exchange, as inspect's messages: the instructions first, as the
    system message they went out as, then each part of each message.
    """
    said: list[ChatMessage] = []

    for message in messages:
        if isinstance(message, ModelResponse):
            said.append(assistant(message))
            continue

        if message.instructions and not said:
            said.append(ChatMessageSystem(content=message.instructions))

        said += [
            said_part
            for part in message.parts
            if (said_part := _request_part(part)) is not None
        ]

    return said


def assistant(response: ModelResponse) -> ChatMessageAssistant:
    """A response: what the LLM thought and wrote, and the tools it called."""
    content: list[Content] = []
    calls: list[ToolCall] = []

    for part in response.parts:
        match part:
            case ThinkingPart():
                content.append(
                    ContentReasoning(reasoning=part.content, signature=part.signature)
                )
            case TextPart():
                content.append(ContentText(text=part.content))
            case ToolCallPart():
                calls.append(_tool_call(part))
            case _:
                pass

    return ChatMessageAssistant(
        content=content or "",
        tool_calls=calls or None,
        model=response.model_name,
    )


def output(model: str, response: ModelResponse | None) -> ModelOutput:
    """A response, as the output of the call that asked for it."""
    if response is None:
        return ModelOutput(model=model)

    return ModelOutput(
        model=model,
        choices=[
            ChatCompletionChoice(
                message=assistant(response),
                stop_reason=stop_reason(response.finish_reason),
            )
        ],
        usage=usage([response]),
    )


def stop_reason(finish_reason: str | None) -> StopReason:
    return STOP_REASONS.get(finish_reason or "", "unknown")


def usage(responses: Iterable[ModelResponse]) -> ModelUsage | None:
    """The tokens the responses took, summed, or None where there were none."""
    total: ModelUsage | None = None

    for response in responses:
        used = response.usage
        this = ModelUsage(
            input_tokens=used.input_tokens,
            output_tokens=used.output_tokens,
            total_tokens=used.input_tokens + used.output_tokens,
            input_tokens_cache_read=used.cache_read_tokens or None,
            input_tokens_cache_write=used.cache_write_tokens or None,
            reasoning_tokens=used.details.get("reasoning_tokens"),
        )
        total = this if total is None else total + this

    return total


def generate_config(sent: str) -> GenerateConfig:
    """
    The settings a request went out with, as inspect's: those it has a
    field for as those fields, the rest as its extra body.
    """
    request: dict[str, Any] = json.loads(sent)
    fields: dict[str, Any] = {}
    extra: dict[str, Any] = {}

    for key, value in request.items():
        if key in GENERATE_CONFIG:
            fields[GENERATE_CONFIG[key]] = value
        elif key not in NOT_SETTINGS:
            extra[key] = value

    if isinstance(fields.get("stop_seqs"), str):
        fields["stop_seqs"] = [fields["stop_seqs"]]

    return GenerateConfig(**fields, extra_body=extra or None)


def body(text: str) -> dict[str, JsonValue]:
    """
    A body sent or received, as JSON: a streamed response as the one
    completion its chunks make up, as inspect keeps a streamed response, and
    one that is neither as its text. The bytes themselves are the run's.
    """
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        chunks: list[dict[str, Any]] = []

        for line in text.splitlines():
            data = line.removeprefix("data:").strip()

            if not line.startswith("data:") or data == "[DONE]":
                continue

            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                return {"text": text}

            if isinstance(chunk, dict):
                chunks.append(cast(dict[str, Any], chunk))

        return _completion(chunks) if chunks else {"text": text}

    if isinstance(value, dict):
        return cast(dict[str, JsonValue], value)

    return {"body": cast(JsonValue, value)}


def _completion(chunks: list[dict[str, Any]]) -> dict[str, JsonValue]:
    """
    A stream's chunks joined into the completion a request that didn't stream
    would have had: each choice's deltas joined into its message, a tool
    call's pieces into the call, and the usage the last chunk reports.
    """
    choices: dict[int, dict[str, Any]] = {}
    usage: JsonValue = None

    for chunk in chunks:
        usage = chunk.get("usage") or usage

        streamed: list[dict[str, Any]] = chunk.get("choices") or []

        for choice in streamed:
            index: int = choice.get("index", 0)
            joined = choices.setdefault(
                index,
                {
                    "index": index,
                    "message": {"role": "assistant"},
                    "finish_reason": None,
                },
            )
            message: dict[str, Any] = joined["message"]
            delta: dict[str, Any] = choice.get("delta") or {}

            for key, value in delta.items():
                if key == "tool_calls":
                    _join_tool_calls(message.setdefault("tool_calls", []), value)
                elif isinstance(value, str) and key != "role":
                    message[key] = message.get(key, "") + value
                elif value is not None and key != "role":
                    message[key] = value

            joined["finish_reason"] = (
                choice.get("finish_reason") or joined["finish_reason"]
            )

    first = chunks[0]

    return {
        "id": first.get("id"),
        "object": "chat.completion",
        "created": first.get("created"),
        "model": first.get("model"),
        "choices": [choices[index] for index in sorted(choices)],
        "usage": usage,
    }


def _join_tool_calls(calls: list[dict[str, Any]], deltas: list[dict[str, Any]]) -> None:
    for delta in deltas:
        index: int = delta.get("index", len(calls))

        while len(calls) <= index:
            calls.append({"function": {"name": "", "arguments": ""}})

        call = calls[index]
        function: dict[str, str] = call["function"]
        pieces: dict[str, Any] = delta.get("function") or {}

        for key in ("id", "type"):
            if delta.get(key):
                call[key] = delta[key]

        for key, value in pieces.items():
            if isinstance(value, str):
                function[key] = function.get(key, "") + value


def _request_part(part: ModelRequestPart) -> ChatMessage | None:
    """A part of a request, where it is one the LLM was sent as a message."""
    match part:
        case SystemPromptPart():
            return ChatMessageSystem(content=part.content)
        case UserPromptPart():
            return ChatMessageUser(content=_user_content(part.content))
        case ToolReturnPart():
            return ChatMessageTool(
                content=part.model_response_str(),
                tool_call_id=part.tool_call_id,
                function=part.tool_name,
            )
        case RetryPromptPart(tool_name=None):
            return ChatMessageUser(content=part.model_response())
        case RetryPromptPart():
            return ChatMessageTool(
                content=part.model_response(),
                tool_call_id=part.tool_call_id,
                function=part.tool_name,
                error=ToolCallError("parsing", part.model_response()),
            )
        case _:
            return None


def _user_content(content: str | Sequence[Any]) -> str | list[Content]:
    if isinstance(content, str):
        return content

    return [
        ContentText(text=item if isinstance(item, str) else repr(item))
        for item in content
    ]


def _tool_call(part: ToolCallPart) -> ToolCall:
    """A call, with why its arguments aren't an object where they aren't."""
    arguments: Any = part.args or {}
    problem: str | None = None

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as e:
            problem = f"the arguments aren't JSON: {e}"

    if problem is None and not isinstance(arguments, dict):
        problem = "the arguments aren't an object"

    return ToolCall(
        id=part.tool_call_id,
        function=part.tool_name,
        arguments={} if problem else cast(dict[str, Any], arguments),
        parse_error=problem,
    )

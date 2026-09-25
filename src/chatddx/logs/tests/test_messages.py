"""pydantic-ai's messages as inspect's, and the bodies a run sent and got."""

import json
from typing import Any

from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageTool,
    ContentReasoning,
)
from inspect_ai.tool import ToolCall
from pydantic_ai import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from chatddx.logs.messages import body, chat_messages, generate_config, stop_reason


def test_the_instructions_come_first_as_the_system_message_they_went_out_as():
    said = chat_messages(
        [
            ModelRequest(
                parts=[UserPromptPart("a vignette")], instructions="Be brief."
            ),
            ModelResponse(
                parts=[ThinkingPart("so"), TextPart("an answer")], model_name="m"
            ),
            ModelRequest(parts=[UserPromptPart("and?")], instructions="Be brief."),
        ]
    )

    assert [(message.role, message.text) for message in said] == [
        ("system", "Be brief."),
        ("user", "a vignette"),
        ("assistant", "an answer"),
        ("user", "and?"),
    ]
    assert isinstance(said[2], ChatMessageAssistant)
    assert said[2].content[0] == ContentReasoning(reasoning="so")
    assert said[2].model == "m"


def test_a_tool_call_and_what_it_returned():
    call, returned = chat_messages(
        [
            ModelResponse(parts=[ToolCallPart("look_up", {"q": "x"}, "c1")]),
            ModelRequest(parts=[ToolReturnPart("look_up", "found", "c1")]),
        ]
    )

    assert isinstance(call, ChatMessageAssistant)
    assert call.tool_calls == [
        ToolCall(id="c1", function="look_up", arguments={"q": "x"})
    ]
    assert isinstance(returned, ChatMessageTool)
    assert (returned.text, returned.function, returned.tool_call_id) == (
        "found",
        "look_up",
        "c1",
    )


def test_a_call_whose_arguments_dont_parse_says_why():
    [call] = chat_messages(
        [ModelResponse(parts=[ToolCallPart("look_up", "{no", "c1")])]
    )

    assert isinstance(call, ChatMessageAssistant)
    assert call.tool_calls
    assert call.tool_calls[0].arguments == {}
    assert call.tool_calls[0].parse_error


def test_a_retry_for_a_tool_is_that_tools_error():
    [retried] = chat_messages(
        [
            ModelRequest(
                parts=[
                    RetryPromptPart(
                        "v1 is missing", tool_name="look_up", tool_call_id="c1"
                    )
                ]
            )
        ]
    )

    assert isinstance(retried, ChatMessageTool)
    assert retried.error is not None
    assert retried.error.type == "parsing"
    assert "v1 is missing" in retried.error.message


def test_a_finish_reason_is_inspects_stop_reason():
    assert [stop_reason(reason) for reason in ("stop", "length", "tool_call")] == [
        "stop",
        "max_tokens",
        "tool_calls",
    ]
    assert stop_reason(None) == "unknown"


def test_a_streamed_response_is_the_completion_its_chunks_make_up():
    def chunk(delta: dict[str, Any], finish: str | None = None) -> dict[str, Any]:
        return {
            "id": "c",
            "created": 1,
            "model": "m",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }

    call = {"index": 0, "id": "t1", "type": "function"}
    chunks: list[dict[str, Any]] = [
        chunk({"role": "assistant", "content": ""}),
        chunk({"reasoning": "let me "}),
        chunk({"reasoning": "look"}),
        chunk({"content": "Look", "reasoning": None}),
        chunk({"content": "ing."}),
        chunk(
            {
                "tool_calls": [
                    {**call, "function": {"name": "look_up", "arguments": '{"q"'}}
                ]
            }
        ),
        chunk({"tool_calls": [{"index": 0, "function": {"arguments": ': "x"}'}}]}),
        chunk({}, "tool_calls"),
        {
            "id": "c",
            "choices": [],
            "usage": {"prompt_tokens": 3, "completion_tokens": 9},
        },
    ]
    streamed = (
        "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
    )

    assert body(streamed) == {
        "id": "c",
        "object": "chat.completion",
        "created": 1,
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Looking.",
                    "reasoning": "let me look",
                    "tool_calls": [
                        {
                            "id": "t1",
                            "type": "function",
                            "function": {"name": "look_up", "arguments": '{"q": "x"}'},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 9},
    }


def test_a_body_that_is_json_is_kept_as_it_is():
    assert body('{"error": {"message": "no"}}') == {"error": {"message": "no"}}
    assert body("[1, 2]") == {"body": [1, 2]}
    assert body("Bad Gateway") == {"text": "Bad Gateway"}


def test_a_requests_settings_are_inspects_where_it_has_a_place_for_them():
    config = generate_config(
        json.dumps(
            {
                "messages": [{"role": "user", "content": "a vignette"}],
                "model": "m",
                "stream": True,
                "temperature": 0.6,
                "top_k": 20,
                "stop": "END",
                "seed": 7,
                "response_format": {"type": "json_schema"},
                "chat_template_kwargs": {"enable_thinking": False},
            }
        )
    )

    assert (config.temperature, config.top_k, config.stop_seqs, config.seed) == (
        0.6,
        20,
        ["END"],
        7,
    )
    assert config.extra_body == {"chat_template_kwargs": {"enable_thinking": False}}

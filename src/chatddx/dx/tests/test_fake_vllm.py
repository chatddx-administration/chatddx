import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from jsonschema.validators import validator_for

from chatddx.core import settings
from chatddx.dx.fake_vllm import (
    ANSWER,
    completion,
    instance,
    respond,
    server,
    stream,
    thinking,
)

QWEN = "Qwen/Qwen3-8B-AWQ"
GPT_OSS = "openai/gpt-oss-20b"

SCHEMAS = sorted((settings.INVENTORY_PATH / "inventory/schemas").glob("*.json"))


def body(model: str = QWEN, **fields: Any) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": "a cough"}],
        "stream": True,
    } | fields


def test_qwen3_thinks_unless_told_not_to():
    assert thinking(body()) is not None
    assert thinking(body(chat_template_kwargs={"enable_thinking": False})) is None


def test_gpt_oss_always_thinks():
    assert thinking(body(GPT_OSS, chat_template_kwargs={"enable_thinking": False}))


def test_an_llm_of_no_family_it_knows_doesn_t_think():
    assert thinking(body("meta-llama/Llama-3.1-8B")) is None


def test_it_thinks_about_the_fields_it_was_sent():
    thought = thinking(body(GPT_OSS, reasoning_effort="low", temperature=1.0))

    assert thought is not None
    assert 'reasoning_effort="low" temperature=1.0' in thought
    assert "user (2 words)" in thought


def test_it_reads_back_a_schema_or_a_tool_by_what_it_is():
    thought = thinking(
        body(
            response_format={"type": "json_schema", "json_schema": {"schema": {}}},
            tools=[{"type": "function", "function": {"name": "final_result"}}],
        )
    )

    assert thought is not None
    assert "response_format=json_schema tools=final_result" in thought


def test_a_budget_cuts_the_thinking_short():
    reply = respond(body(thinking_token_budget=3))

    assert reply.reasoning == "I am the "
    assert (reply.content, reply.finish) == (ANSWER, "stop")


def test_max_tokens_are_spent_on_thinking_first():
    reply = respond(body(max_completion_tokens=5))

    assert (reply.reasoning, reply.content, reply.finish) == (
        "I am the fake vLLM, ",
        "",
        "length",
    )
    assert respond(body(max_tokens=5)) == reply


def test_without_a_reasoning_parser_the_thinking_stays_in_the_content():
    reply = respond(body(), reasoning_parser=False)

    assert reply.reasoning is None
    assert reply.content == f"<think>\n{thinking(body())}\n</think>\n\n{ANSWER}"


def test_without_a_reasoning_parser_a_grammar_leaves_no_room_to_think():
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    held = respond(
        body(
            response_format={"type": "json_schema", "json_schema": {"schema": schema}}
        ),
        reasoning_parser=False,
    )
    required = respond(
        body(tools=[function("final_result")], tool_choice="required"),
        reasoning_parser=False,
    )

    assert (held.reasoning, json.loads(held.content)) == (None, {"ok": False})
    assert (required.reasoning, required.content) == (None, "")
    assert required.call == ("final_result", "null")


# ------------------------------------------------------------------ schemas


@pytest.mark.parametrize("path", SCHEMAS, ids=lambda path: path.stem)
def test_what_it_writes_holds_to_the_inventory_s_schemas(path: Path):
    schema = json.loads(path.read_text())

    assert not list(validator_for(schema)(schema).iter_errors(instance(schema)))


def test_what_it_writes_follows_references_unions_and_counts():
    schema = {
        "$defs": {
            "Diagnosis": {"type": "object", "properties": {"name": {"type": "string"}}}
        },
        "type": "object",
        "properties": {
            "diagnoses": {
                "type": "array",
                "items": {"$ref": "#/$defs/Diagnosis"},
                "minItems": 2,
                "maxItems": 2,
            },
            "severity": {"enum": ["high", "low"]},
            "kind": {"const": "plan"},
            "maybe": {"anyOf": [{"type": "null"}, {"type": "integer"}]},
        },
    }

    assert instance(schema) == {
        "diagnoses": [{"name": "fake name 1"}, {"name": "fake name 2"}],
        "severity": "high",
        "kind": "plan",
        "maybe": 1,
    }


def test_held_to_a_schema_it_answers_with_a_document_that_holds():
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    reply = respond(
        body(response_format={"type": "json_schema", "json_schema": {"schema": schema}})
    )

    assert json.loads(reply.content) == {"ok": False}


def test_shown_a_schema_it_answers_with_a_document_that_holds():
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    shown = {"role": "system", "content": f"Answer with this:\n{json.dumps(schema)}"}
    reply = respond(body(messages=[shown, {"role": "user", "content": "a cough"}]))

    assert json.loads(reply.content) == {"ok": False}


def test_offered_a_tool_it_calls_it():
    tool = {
        "type": "function",
        "function": {
            "name": "final_result",
            "parameters": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
        },
    }
    reply = respond(body(tools=[tool]))

    assert reply.call == ("final_result", '{"ok": false}')
    assert (reply.content, reply.finish) == ("", "tool_calls")


def function(name: str) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "parameters": {}}}


def called(*names: str) -> list[dict[str, Any]]:
    """A conversation in which the LLM called `names`, one a round."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": "a cough"}]

    for n, name in enumerate(names):
        messages += [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call-{n}",
                        "type": "function",
                        "function": {"name": name, "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": f"call-{n}", "content": "done"},
        ]

    return messages


def test_offered_tools_it_calls_each_once_then_answers():
    tools = [function("lookup"), function("now")]

    assert respond(body(tools=tools)).call == ("lookup", "null")
    assert respond(body(tools=tools, messages=called("lookup"))).call == (
        "now",
        "null",
    )

    reply = respond(body(tools=tools, messages=called("lookup", "now")))
    assert (reply.call, reply.content, reply.finish) == (None, ANSWER, "stop")


def test_offered_the_final_result_tool_too_it_answers_through_it_last():
    tools = [function("final_result"), function("lookup")]

    assert respond(body(tools=tools)).call == ("lookup", "null")
    assert respond(body(tools=tools, messages=called("lookup"))).call == (
        "final_result",
        "null",
    )


# ------------------------------------------------------------------ streams


def events(chunks: Iterator[str]) -> list[Any]:
    lines = [chunk.removeprefix("data: ").strip() for chunk in chunks]
    assert lines[-1] == "[DONE]"
    return [json.loads(line) for line in lines[:-1]]


def test_it_streams_the_thinking_then_the_answer_then_the_usage():
    chunks = events(stream(body(stream_options={"include_usage": True})))
    deltas = [c["choices"][0]["delta"] for c in chunks if c["choices"]]

    assert deltas[0] == {"role": "assistant", "content": ""}
    assert "".join(d.get("reasoning", "") for d in deltas) == thinking(body())
    assert "".join(d.get("content", "") for d in deltas) == ANSWER
    assert chunks[-2]["choices"][0]["finish_reason"] == "stop"
    assert chunks[-1]["usage"]["prompt_tokens"] == 2


def test_it_streams_a_call_as_its_name_then_its_arguments():
    tool: dict[str, Any] = {
        "type": "function",
        "function": {"name": "final_result", "parameters": {}},
    }
    chunks = events(stream(body(tools=[tool])))
    calls = [
        call
        for c in chunks
        if c["choices"]
        for call in c["choices"][0]["delta"].get("tool_calls", [])
    ]

    assert calls[0]["function"] == {"name": "final_result", "arguments": ""}
    assert "".join(call["function"]["arguments"] for call in calls) == "null"
    assert chunks[-1]["choices"][0]["finish_reason"] == "tool_calls"


def test_it_answers_whole_when_asked_not_to_stream():
    response = completion(body(GPT_OSS, stream=False))
    message = response["choices"][0]["message"]

    assert message["content"] == ANSWER
    assert message["reasoning"] == thinking(body(GPT_OSS))


@pytest.fixture
def fake_url() -> Iterator[str]:
    fake = server("127.0.0.1", 0)
    host, port = fake.server_address[:2]
    thread = threading.Thread(target=fake.serve_forever, daemon=True)
    thread.start()

    yield f"http://{host!s}:{port}"

    fake.shutdown()
    fake.server_close()


def test_it_serves_chat_completions_over_http(fake_url: str):
    response = httpx2.post(
        f"{fake_url}/v1/chat/completions", json=body(QWEN, stream=False)
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == ANSWER


def test_it_serves_nothing_else(fake_url: str):
    assert httpx2.post(f"{fake_url}/v1/completions", json={}).status_code == 404

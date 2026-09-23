import json
import threading
from collections.abc import Iterator
from typing import Any

import httpx2
import pytest

from chatddx.dx.fake_vllm import ANSWER, completion, respond, server, stream, thinking

QWEN = "Qwen/Qwen3-8B-AWQ"
GPT_OSS = "openai/gpt-oss-20b"


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


def test_a_model_of_no_family_it_knows_doesn_t_think():
    assert thinking(body("meta-llama/Llama-3.1-8B")) is None


def test_it_thinks_about_the_fields_it_was_sent():
    thought = thinking(body(GPT_OSS, reasoning_effort="low", temperature=1.0))

    assert thought is not None
    assert 'reasoning_effort="low" temperature=1.0' in thought
    assert "user (2 words)" in thought


def test_a_budget_cuts_the_thinking_short():
    reasoning, answer, finish = respond(body(thinking_token_budget=3))

    assert reasoning == "I am the "
    assert (answer, finish) == (ANSWER, "stop")


def test_max_tokens_are_spent_on_thinking_first():
    reasoning, answer, finish = respond(body(max_completion_tokens=5))

    assert (reasoning, answer, finish) == ("I am the fake vLLM, ", "", "length")
    assert respond(body(max_tokens=5)) == (reasoning, answer, finish)


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

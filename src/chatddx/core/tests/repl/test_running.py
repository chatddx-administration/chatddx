"""A case run on the cell streams as it comes, is judged, and is recorded."""

import json
import re
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from chatddx.dx.fake_vllm import FakeTransport, stream
from chatddx.history.models import RunModel, TrialModel
from chatddx.repo.entities.tool.django import ToolBranchModel

type Say = Callable[..., str]
type SayThrough = Callable[[Any], Say]

pytestmark = pytest.mark.django_db


def streaming(body: dict[str, Any]) -> httpx2.Response:
    """What the fake vLLM streams back for `body`."""
    return httpx2.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content="".join(stream(body)).encode(),
    )


def failing(_request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(400, json={"error": {"message": "no such model"}})


def test_run_streams_a_trial_of_the_cell(say: Say, fake: FakeTransport):
    written = say("cell free-text qwen3-8b-awq@fake", "run case-1")

    assert "trial: free-text × qwen3-8b-awq@fake × case-1" in written
    assert "[thinking] I am the fake vLLM" in written
    assert "Fake diagnosis A\nFake diagnosis B\nFake diagnosis C" in written

    [request] = fake.requests
    assert request["messages"][-1] == {"role": "user", "content": "case payload 1"}


def test_each_run_is_recorded_as_a_run_of_its_trial(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "run case-1 7", "run case-1 7")

    first, again = re.findall(r"recorded as run (\d+) of trial (\w{8})", written)

    assert (first[0], again[0]) == ("1", "2")
    assert first[1] == again[1]

    [trial] = TrialModel.objects.all()
    assert str(trial.uuid).startswith(first[1])
    assert trial.runs.filter(status="completed").count() == 2


def test_a_run_whose_server_fails_is_recorded_as_errored(say_through: SayThrough):
    say = say_through(httpx2.MockTransport(failing))

    written = say("cell free-text qwen3-8b-awq@fake", "run case-1")

    assert "recorded as run 1 of trial" in written

    [run] = RunModel.objects.all()
    assert run.status == "errored"
    assert run.error is not None and "no such model" in run.error
    assert run.responses == ['{"error":{"message":"no such model"}}']
    assert run.session is not None
    request, response, error = run.session.messages.all()
    assert (request.kind, response.kind, error.kind) == ("request", "response", "error")
    assert response.payload["state"] == "interrupted"


def test_run_sends_nothing_for_a_refused_cell(say: Say, fake: FakeTransport):
    written = say("cell baseline gpt-oss-20b@fake", "set reasoning off", "run case-1")

    assert "refused: reasoning: always reasons" in written
    assert fake.requests == []


def test_run_needs_a_whole_cell(say: Say, fake: FakeTransport):
    written = say("use free-text", "run case-1")

    assert "the cell needs a configuration and a stack" in written
    assert fake.requests == []


def test_run_takes_the_trial_s_seed(say: Say, fake: FakeTransport):
    written = say("cell free-text qwen3-8b-awq@fake", "run case-1 42", "run case-1 x")

    assert "trial: free-text × qwen3-8b-awq@fake × case-1 (seed 42)" in written
    assert fake.requests[0]["seed"] == 42
    assert "a seed is a whole number, not 'x'" in written
    assert len(fake.requests) == 1


def test_a_structured_answer_is_judged_and_its_views_read(say: Say):
    written = say("cell plan qwen3-8b-awq@fake", "run case-1")

    assert '"acute_warning": "fake acute warning"' in written
    assert "valid" in written
    assert "differential\n  1. fake diagnosis 1\n  2. fake diagnosis 2" in written


def test_free_text_has_its_views_read_too(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "run case-1")

    assert "differential\n  1. Fake diagnosis A" in written
    assert "valid" not in written


def test_tool_mode_shows_the_call_the_answer_is_given_through(say: Say):
    written = say("cell diagnoses-tool qwen3-8b-awq@fake", "run case-1")

    assert '[final_result] {"diagnoses": ["fake diagnoses 1"' in written
    assert "valid" in written


def test_an_answer_that_doesn_t_hold_says_why(say_through: SayThrough):
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        body["response_format"] = {"type": "json_object"}
        return streaming(body)

    say = say_through(httpx2.MockTransport(handler))

    written = say("cell plan qwen3-8b-awq@fake", "run case-1")

    assert "invalid: $: 'acute_warning' is a required property" in written
    assert "differential\n  nothing" in written


def test_an_answer_that_doesn_t_parse_says_so(say_through: SayThrough):
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return streaming({"model": "Qwen/Qwen3-8B-AWQ", "messages": []})

    say = say_through(httpx2.MockTransport(handler))

    written = say("cell challenge-coercion-prompted qwen3-8b-awq@fake", "run case-1")

    assert (
        "invalid: the answer doesn't parse: Invalid JSON: expected value at line 1"
        in written
    )


def test_a_run_says_when_no_thinking_came_back_though_it_was_asked_for(
    say_through: SayThrough,
):
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        body["chat_template_kwargs"] = {"enable_thinking": False}
        return streaming(body)

    say = say_through(httpx2.MockTransport(handler))

    written = say("cell diagnoses qwen3-8b-awq@fake", "run case-1")

    assert "no thinking came back, though reasoning resolved to 'on'" in written
    assert "valid" in written


def test_thinking_no_reasoning_parser_took_out_is_labelled_so(
    say_through: SayThrough,
):
    say = say_through(FakeTransport(reasoning_parser=False))

    written = say("cell free-text qwen3-8b-awq@fake", "run case-1")

    assert "[thinking in content] I am the fake vLLM" in written
    assert "Fake diagnosis A" in written
    assert "no thinking came back" not in written


def test_calls_and_what_they_returned_stream_as_they_come(
    say: Say, fake: FakeTransport
):
    written = say("cell test-tools qwen3-8b-awq@fake", "run case-1")

    assert "[sentinel_string] {}\n[result] asdf" in written
    assert '[sentinel_op] {"v1": 1, "v2": 1}\n[result] 0' in written
    assert "Fake diagnosis A" in written
    assert "3 requests)" in written
    assert len(fake.requests) == 3


def test_a_toolset_can_be_set_in_any_configuration(say: Say, fake: FakeTransport):
    written = say(
        "cell baseline qwen3-8b-awq@fake", "set toolset sentinel", "run case-1"
    )

    assert "[result] asdf" in written
    assert [t["function"]["name"] for t in fake.requests[0]["tools"]] == [
        "sentinel_string",
        "sentinel_op",
    ]


def test_a_model_still_calling_tools_is_stopped(say_through: SayThrough):
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        return streaming(body | {"messages": body["messages"][:1]})

    say = say_through(httpx2.MockTransport(handler))

    written = say("cell test-tools qwen3-8b-awq@fake", "run case-1")

    assert "stopped: still calling tools after 5 rounds" in written


def test_a_tool_with_nothing_to_run_is_said_before_anything_is_sent(
    say: Say, fake: FakeTransport
):
    _ = ToolBranchModel.objects.filter(name="sentinel_op").update(details={})

    written = say("cell test-tools qwen3-8b-awq@fake", "run case-1")

    assert "nothing to run for sentinel_op: no implementation" in written
    assert fake.requests == []

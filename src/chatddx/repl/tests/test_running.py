import asyncio
import json
import re
import signal
from collections.abc import Callable
from typing import Any, override

import httpx2
import pytest
from rich.console import Console

from chatddx.dev.fake_vllm import FakeTransport, completion, stream
from chatddx.history.models import RunModel, TrialModel
from chatddx.history.record import record
from chatddx.repl import running
from chatddx.repl.shell import SEEDS, Repl
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import CaseBranchDetails
from chatddx.repo.entities.tool.django import ToolBranchModel
from chatddx.repo.store.branch import commit

type Say = Callable[..., str]
type SayThrough = Callable[[Any], Say]

pytestmark = pytest.mark.django_db


def streaming(body: dict[str, Any]) -> httpx2.Response:
    return httpx2.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content="".join(stream(body)).encode(),
    )


def failing(_request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(400, json={"error": {"message": "no such model"}})


def test_run_streams_a_run_of_the_cell(say: Say, fake: FakeTransport):
    written = say("cell free-text qwen3-8b-awq@fake", "run case-1")

    assert "trial: free-text × qwen3-8b-awq@fake × case-1" in written
    assert "[thinking] I am the fake vLLM" in written
    assert "Fake diagnosis A\nFake diagnosis B\nFake diagnosis C" in written

    [request] = fake.requests
    assert request["messages"][-1] == {"role": "user", "content": "case vignette 1"}
    assert fake.aborted == []


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
    assert run.conversation is not None
    request, response, error = run.conversation.messages.all()
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
    assert "a seed is a whole number up to" in written
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


def test_an_llm_still_calling_tools_is_stopped(say_through: SayThrough):
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

    assert "the tool 'sentinel_op' has nothing to run" in written
    assert "trial:" not in written
    assert fake.requests == []


def test_a_tool_that_isn_t_chatddx_s_own_is_refused_before_anything_is_sent(
    say: Say, fake: FakeTransport
):
    _ = ToolBranchModel.objects.filter(name="sentinel_op").update(
        details={"implementation": {"function": "os:system"}}
    )

    written = say("cell test-tools qwen3-8b-awq@fake", "run case-1")

    assert (
        "the tool 'sentinel_op' can't run: os:system isn't one of chatddx's own"
        in written
    )
    assert fake.requests == []


class Interrupting(FakeTransport):
    def __init__(self, after: int, presses: int = 1, waits: bool = True):
        super().__init__()
        self.after: int = after
        self.presses: int = presses
        self.waits: bool = waits
        self.pressed: bool = False

    @override
    async def next_token(self, generated: int, /) -> None:
        if generated == self.after and not self.pressed:
            self.pressed = True

            for _ in range(self.presses):
                signal.raise_signal(signal.SIGINT)

            if self.waits:
                await asyncio.sleep(10)


def pressing(say: Say, *lines: str) -> str:
    try:
        return say(*lines)
    except KeyboardInterrupt:
        pytest.fail("Ctrl-C got past the command")
    finally:
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def line_of(written: str, start: str) -> str:
    [line] = [line for line in written.splitlines() if line.startswith(start)]
    return line


def row(written: str, case: str) -> list[str]:
    """The words of the batch line of `case`."""
    return line_of(written, f"{case} ").split()


def under(written: str, case: str, scorer: str) -> str:
    at = line_of(written, "case ").index(scorer)
    return line_of(written, f"{case} ")[at : at + len(scorer)].strip()


def test_batch_runs_the_cell_on_each_case_tagged_a_line_to_each(
    say: Say, fake: FakeTransport
):
    written = say("cell plan qwen3-8b-awq@fake", "batch tag-2")

    assert "batch: plan × qwen3-8b-awq@fake × 2 cases tagged tag-2" in written
    assert [request["messages"][-1]["content"] for request in fake.requests] == [
        "case vignette 1",
        "case vignette 2",
    ]
    assert row(written, "case-1")[2:] == ["valid", "0", "0.5", "1"]
    assert row(written, "case-2")[2:] == ["valid", "0"]

    # case-2 expects no warning, nor a disposition
    assert under(written, "case-2", "reciprocal_rank") == "0"
    assert under(written, "case-2", "warning_mentions") == ""
    assert under(written, "case-1", "warning_mentions") == "1"

    assert ["reciprocal_rank", "2", "0.25", "0.25"] in [
        line.split() for line in written.splitlines()
    ]
    assert sorted(
        RunModel.objects.values_list("conversation__description", flat=True)
    ) == [
        "plan × qwen3-8b-awq@fake × case-1",
        "plan × qwen3-8b-awq@fake × case-2",
    ]


def test_a_batch_line_counts_the_output_tokens_the_server_counted(
    say: Say, fake: FakeTransport
):
    written = say("cell free-text qwen3-8b-awq@fake", "batch tag-1")

    counted = completion(fake.requests[0])["usage"]["completion_tokens"]
    assert row(written, "case-1")[:3] == ["case-1", str(counted), "completed"]


def test_batch_runs_the_cases_with_any_of_its_tags(say: Say, fake: FakeTransport):
    written = say("cell free-text qwen3-8b-awq@fake", "batch tag-1")

    assert "1 case tagged tag-1" in written
    assert len(fake.requests) == 1

    written = say("batch nope tag-1 tag-2")

    assert "2 cases tagged nope or tag-1 or tag-2" in written
    assert len(fake.requests) == 3

    assert "no case tagged nope for alex" in say("batch nope")
    assert "usage: batch TAG..." in say("batch")
    assert len(fake.requests) == 3


def test_a_case_under_two_names_runs_once(say: Say, fake: FakeTransport):
    case = CaseBranchModel.objects.filter(owner__name="archive", name="case-1").latest(
        "pk"
    )
    _ = commit(
        case.trail, CaseBranchDetails(name="case-1-again", owner="alex", tags=["tag-1"])
    )

    written = say("cell free-text qwen3-8b-awq@fake", "batch tag-1")

    assert "1 case tagged tag-1" in written
    assert len(fake.requests) == 1


def test_batch_sends_nothing_for_a_cell_that_can_t_run(say: Say, fake: FakeTransport):
    written = say(
        "batch tag-1",
        "cell baseline gpt-oss-20b@fake",
        "set reasoning off",
        "batch tag-1",
    )

    assert "the cell needs a configuration and a stack" in written
    assert "refused: reasoning: always reasons" in written
    assert fake.requests == []


def test_a_run_that_fails_is_said_on_its_line_and_the_batch_goes_on(
    say_through: SayThrough,
):
    say = say_through(httpx2.MockTransport(failing))

    written = say("cell free-text qwen3-8b-awq@fake", "batch tag-2")

    for case in ("case-1", "case-2"):
        assert row(written, case)[1:4] == ["0", "errored", "ModelHTTPError:"]

    assert [run.status for run in RunModel.objects.all()] == ["errored", "errored"]
    assert "stopped" not in written


def test_ctrl_c_stops_a_run_as_it_streams_and_it_is_recorded_as_stopped(
    say_through: SayThrough,
):
    transport = Interrupting(after=5)
    say = say_through(transport)

    written = pressing(say, "cell free-text qwen3-8b-awq@fake", "run case-1")

    assert "[thinking] I am the fake" in written
    assert "(stopped)" in written
    assert "recorded as run 1 of trial" in written
    assert transport.aborted == transport.requests

    [run] = RunModel.objects.all()
    assert (run.status, run.error) == ("errored", "stopped")
    assert run.conversation is not None
    request, response, error = run.conversation.messages.all()
    assert (request.kind, response.kind, error.kind) == ("request", "response", "error")
    assert response.payload["state"] == "interrupted"


def test_ctrl_c_lets_the_run_under_way_finish_then_stops_the_batch(
    say_through: SayThrough,
):
    transport = Interrupting(after=5, waits=False)
    say = say_through(transport)

    written = pressing(say, "cell free-text qwen3-8b-awq@fake", "batch tag-2")

    assert row(written, "case-1")[2:] == ["completed", "17", "0.5"]
    assert "case-2 " not in written
    assert "stopped after 1 of 2 cases" in written
    assert len(transport.requests) == 1
    assert transport.aborted == []
    assert RunModel.objects.get().status == "completed"


def test_ctrl_c_again_stops_the_run_under_way_too(say_through: SayThrough):
    transport = Interrupting(after=5, presses=2)
    say = say_through(transport)

    written = pressing(say, "cell free-text qwen3-8b-awq@fake", "batch tag-2")

    tokens = row(written, "case-1")[1]
    assert re.fullmatch(r"~[1-5]", tokens)
    assert row(written, "case-1")[2:] == ["errored", "stopped"]
    assert "stopped after 1 of 2 cases" in written
    assert transport.aborted == transport.requests

    [run] = RunModel.objects.all()
    assert (run.status, run.error) == ("errored", "stopped")


def test_ctrl_c_waits_for_a_run_to_be_written_down_then_stops_the_batch(
    say: Say, fake: FakeTransport, monkeypatch: pytest.MonkeyPatch
):
    def pressed(*args: Any, **kwargs: Any) -> RunModel:
        signal.raise_signal(signal.SIGINT)
        return record(*args, **kwargs)

    monkeypatch.setattr(running, "record", pressed)

    written = pressing(say, "cell free-text qwen3-8b-awq@fake", "batch tag-2")

    assert row(written, "case-1")[2:] == ["completed", "17", "0.5"]
    assert "case-2 " not in written
    assert "stopped after 1 of 2 cases" in written
    assert len(fake.requests) == 1
    assert RunModel.objects.get().scores.count() == 2

    written = pressing(say, "run case-1")

    assert "recorded as run 2 of trial" in written
    assert "scores" in written


def test_ctrl_c_again_is_let_through_to_a_run_being_written_down(
    say: Say, monkeypatch: pytest.MonkeyPatch
):
    def pressed_twice(*args: Any, **kwargs: Any) -> RunModel:
        signal.raise_signal(signal.SIGINT)
        signal.raise_signal(signal.SIGINT)
        return record(*args, **kwargs)

    monkeypatch.setattr(running, "record", pressed_twice)

    written = pressing(say, "cell free-text qwen3-8b-awq@fake", "batch tag-2")

    _, tokens = row(written, "case-1")
    assert tokens.isdigit()
    assert "stopped after 0 of 2 cases" in written
    assert not RunModel.objects.exists()


def test_the_repl_holds_a_seed_drawn_as_it_starts(fake: FakeTransport):
    repl = Repl("alex", Console(record=True, width=200), transport=fake)

    assert repl.seed is not None and 0 <= repl.seed < SEEDS
    assert repl.prompt == f"alex #{repl.seed}> "


def test_seed_draws_holds_and_clears_the_seed(repl: Repl, say: Say):
    assert "seed: #42" in say("seed 42")
    assert repl.prompt == "alex #42> "

    written = say("seed")
    assert repl.seed is not None and f"seed: #{repl.seed}" in written

    assert "runs go unseeded" in say("seed none")
    assert repl.prompt == "alex #none> "

    assert "a seed is a whole number" in say("seed x")
    assert repl.seed is None


def test_run_and_batch_send_the_seed_the_repl_holds(say: Say, fake: FakeTransport):
    written = say(
        "cell free-text qwen3-8b-awq@fake", "seed 42", "batch tag-2", "run case-1"
    )

    assert "2 cases tagged tag-2, seed 42" in written
    assert [request["seed"] for request in fake.requests] == [42, 42, 42]

    assert "recorded as run 2 of trial" in written
    assert TrialModel.objects.count() == 2


def test_a_seed_given_to_run_is_that_run_s_alone(
    repl: Repl, say: Say, fake: FakeTransport
):
    _ = say("cell free-text qwen3-8b-awq@fake", "seed 42", "run case-1 7")

    assert fake.requests[0]["seed"] == 7
    assert repl.seed == 42


def test_unseeded_runs_send_no_seed(say: Say, fake: FakeTransport):
    written = say("cell free-text qwen3-8b-awq@fake", "seed none", "batch tag-1")

    assert "1 case tagged tag-1, unseeded" in written
    assert "seed" not in fake.requests[0]


def test_greedy_sampling_is_refused_a_seed(say: Say, fake: FakeTransport):
    written = say(
        "cell free-text qwen3-8b-awq@fake",
        "set sampling greedy",
        "seed 42",
        "run case-1",
        "batch tag-1",
        "run case-1 7",
    )

    assert written.count("sampling is greedy (temperature 0), which ignores") == 3
    assert fake.requests == []

    _ = say("seed none", "run case-1")

    assert len(fake.requests) == 1

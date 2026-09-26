# pyright: basic
import json
import re
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from django.test import Client

from chatddx.core.models import IdentityModel
from chatddx.dev.fake_vllm import FakeTransport, stream
from chatddx.django.api.tests.conftest import Events, of, parts
from chatddx.history.models import ConversationContext, RunModel, TrialModel
from chatddx.repl.bench import MAX_SEED, SEEDS
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.entities.tool.django import ToolBranchModel

pytestmark = pytest.mark.django_db

type Run = Callable[..., Events]

FREE_TEXT = {"configuration": "free-text", "stack": "qwen3-8b-awq@fake"}


def streaming(body: dict[str, Any]) -> httpx2.Response:
    """What the fake vLLM streams back for `body`."""
    return httpx2.Response(
        200,
        headers={"content-type": "text/event-stream"},
        content="".join(stream(body)).encode(),
    )


def failing(_request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(400, json={"error": {"message": "no such model"}})


def post(client: Client, **spec: Any) -> Any:
    return client.post("/api/runs", spec, content_type="application/json")


def recorded(events: Events) -> dict[str, Any]:
    [last] = of(events, "recorded")
    assert events[-1]["type"] == "recorded"
    return last["run"]


def test_a_run_streams_as_it_comes_and_ends_with_its_record(
    run: Run, fake: FakeTransport
):
    events = run(**FREE_TEXT, case="case-1", seed=5)

    assert events[0]["type"] == "run"
    assert events[0]["description"] == (
        "free-text × qwen3-8b-awq@fake × case-1 (seed 5)"
    )
    assert (events[0]["case"], events[0]["seed"]) == ("case-1", 5)
    assert len(of(events, "thinking")) > 1
    assert "".join(event["text"] for event in of(events, "thinking")).startswith(
        "I am the fake vLLM"
    )
    assert "".join(event["text"] for event in of(events, "text")) == (
        "Fake diagnosis A\nFake diagnosis B\nFake diagnosis C"
    )
    assert of(events, "views")[0]["views"]["differential"] == [
        "Fake diagnosis A",
        "Fake diagnosis B",
        "Fake diagnosis C",
    ]
    assert [score["scorer"] for score in of(events, "scores")[0]["scores"]] == [
        "first_mention",
        "reciprocal_rank",
    ]

    run_ = recorded(events)

    assert run_["id"] == events[0]["run"]
    assert (run_["status"], run_["valid"], run_["number"]) == ("completed", None, 1)
    assert run_["case"]["name"] == "case-1"
    assert run_["read"]["stack"]["name"] == "qwen3-8b-awq@fake"
    assert run_["read"]["llm"]["name"] == "qwen3-8b-awq"

    [request] = fake.requests
    assert request["messages"][-1] == {"role": "user", "content": "case vignette 1"}
    conversation = RunModel.objects.get().conversation
    assert conversation is not None
    assert conversation.context == ConversationContext.API


def test_each_run_is_recorded_as_a_run_of_its_trial(run: Run):
    first = recorded(run(**FREE_TEXT, case="case-1", seed=7))
    again = recorded(run(**FREE_TEXT, case="case-1", seed=7))

    assert (first["number"], again["number"]) == (1, 2)
    assert first["trial"] == again["trial"]
    assert first["seed"] == 7

    [trial] = TrialModel.objects.all()
    assert trial.runs.filter(status="completed").count() == 2


def test_a_run_can_be_waited_for_rather_than_watched(alex: Client, fake: FakeTransport):
    response = post(alex, **FREE_TEXT, case="case-1", stream=False)

    assert response.status_code == 200, response.content
    assert response["Content-Type"] == "application/json; charset=utf-8"
    assert response.json()["status"] == "completed"
    assert response.json()["answer"].startswith("Fake diagnosis A")
    assert len(fake.requests) == 1


def test_a_run_whose_server_fails_is_recorded_as_errored(
    run: Run, through: Callable[[Any], None]
):
    through(httpx2.MockTransport(failing))

    events = run(**FREE_TEXT, case="case-1")
    run_ = recorded(events)

    assert "no such model" in of(events, "error")[0]["message"]
    assert of(events, "scores")[0]["scores"] == []
    assert run_["status"] == "errored"
    assert "no such model" in run_["error"]

    [record] = RunModel.objects.all()
    assert record.responses == ['{"error":{"message":"no such model"}}']


def test_a_refused_cell_sends_nothing(alex: Client, fake: FakeTransport):
    response = post(
        alex,
        configuration="baseline",
        stack="gpt-oss-20b@fake",
        reasoning="off",
        case="case-1",
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "the cell is refused on its stack"
    assert [refusal["slice"] for refusal in response.json()["refusals"]] == [
        "reasoning"
    ]
    assert fake.requests == []
    assert not RunModel.objects.exists()


def test_a_run_needs_a_whole_cell_and_a_case(alex: Client, fake: FakeTransport):
    half = post(alex, configuration="free-text", case="case-1")
    caseless = post(alex, **FREE_TEXT)
    both = post(alex, **FREE_TEXT, case="case-1", vignette="a vignette")
    unknown = post(alex, **FREE_TEXT, case="nope")

    assert half.status_code == 400
    assert "needs a configuration and a stack" in half.json()["detail"]
    assert (caseless.status_code, both.status_code) == (422, 422)
    assert unknown.status_code == 404
    assert fake.requests == []


def test_the_seed_is_sent(run: Run, fake: FakeTransport):
    events = run(**FREE_TEXT, case="case-1", seed=42)

    assert events[0]["description"].endswith("× case-1 (seed 42)")
    assert fake.requests[0]["seed"] == 42
    assert recorded(events)["seed"] == 42


def test_a_run_is_seeded_with_a_seed_drawn_unless_told_otherwise(
    run: Run, fake: FakeTransport
):
    drawn = run(**FREE_TEXT, case="case-1")[0]["seed"]
    unseeded = run(**FREE_TEXT, case="case-1", seed="none")

    assert 0 <= drawn < SEEDS
    assert fake.requests[0]["seed"] == drawn
    assert unseeded[0]["seed"] is None
    assert "seed" not in fake.requests[1]
    assert unseeded[0]["description"] == "free-text × qwen3-8b-awq@fake × case-1"
    assert recorded(unseeded)["seed"] is None


def test_greedy_sampling_runs_unseeded_and_is_refused_a_seed(
    alex: Client, run: Run, fake: FakeTransport
):
    greedy = {**FREE_TEXT, "sampling": "greedy", "case": "case-1"}
    refused = post(alex, **greedy, seed=42)

    assert refused.status_code == 422
    assert (
        "sampling is greedy (temperature 0), which ignores"
        in (refused.json()["detail"])
    )
    assert fake.requests == []

    assert run(**greedy)[0]["seed"] is None
    assert "seed" not in fake.requests[0]


def test_a_seed_is_a_whole_number_vllm_takes(alex: Client, fake: FakeTransport):
    for seed in (-1, MAX_SEED + 1, 1.5, "some"):
        assert post(alex, **FREE_TEXT, case="case-1", seed=seed).status_code == 422

    assert fake.requests == []


def test_a_variation_set_in_the_cell_is_sent(run: Run, fake: FakeTransport):
    events = run(**FREE_TEXT, reasoning="off", case="case-1")

    assert events[0]["description"].startswith("free-text+reasoning=off ×")
    assert fake.requests[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert of(events, "thinking") == []
    assert recorded(events)["slices"]["reasoning"]["name"] == "off"


def test_a_vignette_of_one_s_own_runs_as_a_case_without_a_branch(
    run: Run, fake: FakeTransport
):
    events = run(**FREE_TEXT, vignette="a cough, and a fever", seed="none")
    run_ = recorded(events)

    assert fake.requests[0]["messages"][-1]["content"] == "a cough, and a fever"
    assert re.fullmatch(r"[0-9a-f]{6}", run_["case"]["name"])
    assert events[0]["description"].endswith(f"× {run_['case']['name']}")
    assert events[0]["case"] == run_["case"]["name"]
    assert run_["scores"] == []
    assert not CaseBranchModel.objects.filter(trail__vignette__startswith="a cough")


def test_another_s_configuration_runs_once_it_is_one_s_own(
    alex: Client, provision: Callable[..., None], fake: FakeTransport
):
    provision("--with-giftbag", user="bob")

    for branch in ConfigurationBranchModel.objects.filter(owner__name="bob"):
        branch.collaborators.add(IdentityModel.objects.get(name="alex"))

    bobs = {"configuration": "bob/plan", "stack": "qwen3-8b-awq@fake"}
    refused = post(alex, **bobs, case="case-1")

    assert refused.status_code == 403
    assert refused.json()["detail"] == "bob/plan is bob's: save it as your own first"
    assert fake.requests == []

    saved = alex.post(
        "/api/cell/save", {**bobs, "name": "my-plan"}, content_type="application/json"
    )
    assert saved.status_code == 200, saved.content

    ran = post(alex, configuration="my-plan", stack="qwen3-8b-awq@fake", case="case-1")

    assert ran.status_code == 200
    assert b"event: recorded" in b"".join(ran.streaming_content)
    assert len(fake.requests) == 1


def test_a_stack_s_credential_is_one_of_the_identity_s_secrets(
    alex: Client, fake: FakeTransport
):
    for stack in StackBranchModel.objects.filter(name="qwen3-8b-awq@fake"):
        stack.details = {**stack.details, "credential": "fake-key"}
        stack.save()

    missing = post(alex, **FREE_TEXT, case="case-1")

    assert missing.status_code == 409
    assert missing.json()["detail"] == "alex has no secret 'fake-key'"
    assert fake.requests == []

    identity = IdentityModel.objects.get(name="alex")
    identity.secrets = {"fake-key": "sesame"}
    identity.save()

    ran = post(alex, **FREE_TEXT, case="case-1")

    assert ran.status_code == 200
    _ = b"".join(ran.streaming_content)
    assert len(fake.requests) == 1


def test_a_structured_answer_is_judged_and_its_views_read(run: Run):
    events = run(configuration="plan", stack="qwen3-8b-awq@fake", case="case-1")
    views = of(events, "views")[0]["views"]

    assert of(events, "validity") == [
        {"type": "validity", "valid": True, "problem": None}
    ]
    assert views["differential"] == [
        "fake diagnosis 1",
        "fake diagnosis 2",
        "fake diagnosis 3",
    ]
    assert views["warning"] == ["fake acute warning"]
    assert recorded(events)["answer"]["acute_warning"] == "fake acute warning"


def test_an_answer_that_doesn_t_hold_says_why(run: Run, through: Callable[[Any], None]):
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        body["response_format"] = {"type": "json_object"}
        return streaming(body)

    through(httpx2.MockTransport(handler))

    events = run(configuration="plan", stack="qwen3-8b-awq@fake", case="case-1")
    [validity] = of(events, "validity")

    assert validity["valid"] is False
    assert validity["problem"] == "$: 'acute_warning' is a required property"
    assert of(events, "views")[0]["views"]["differential"] == []
    assert recorded(events)["valid"] is False


def test_an_answer_that_doesn_t_parse_says_so(run: Run, through: Callable[[Any], None]):
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return streaming({"model": "Qwen/Qwen3-8B-AWQ", "messages": []})

    through(httpx2.MockTransport(handler))

    events = run(
        configuration="challenge-coercion-prompted",
        stack="qwen3-8b-awq@fake",
        case="case-1",
    )
    run_ = recorded(events)

    assert of(events, "error")[0]["message"].startswith(
        "the answer doesn't parse: Invalid JSON: expected value at line 1"
    )
    assert (run_["status"], run_["valid"], run_["answer"]) == (
        "completed",
        False,
        None,
    )


def test_a_run_says_when_no_thinking_came_back_though_it_was_asked_for(
    run: Run, through: Callable[[Any], None]
):
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        body["chat_template_kwargs"] = {"enable_thinking": False}
        return streaming(body)

    through(httpx2.MockTransport(handler))

    events = run(configuration="diagnoses", stack="qwen3-8b-awq@fake", case="case-1")

    assert of(events, "warning") == [
        {
            "type": "warning",
            "message": "no thinking came back, though reasoning resolved to 'on'",
        }
    ]


def test_thinking_no_reasoning_parser_took_out_is_labelled_so(
    run: Run, through: Callable[[Any], None]
):
    through(FakeTransport(reasoning_parser=False))

    events = run(**FREE_TEXT, case="case-1")

    assert of(events, "thinking")
    assert all(event["in_content"] for event in of(events, "thinking"))
    assert of(events, "warning") == []


def test_calls_and_what_they_returned_stream_as_they_come(
    run: Run, fake: FakeTransport
):
    events = run(configuration="test-tools", stack="qwen3-8b-awq@fake", case="case-1")

    assert [part for part in parts(events) if part[0] != "thinking"][:4] == [
        ("sentinel_string", "{}"),
        ("result sentinel_string", "asdf"),
        ("sentinel_op", '{"v1": 1, "v2": 1}'),
        ("result sentinel_op", "0"),
    ]
    assert of(events, "usage")[0]["requests"] == 3
    assert len(fake.requests) == 3
    assert [tool["name"] for tool in recorded(events)["read"]["tools"]] == [
        "sentinel_string",
        "sentinel_op",
    ]


def test_tool_mode_streams_the_call_the_answer_is_given_through(run: Run):
    events = run(
        configuration="diagnoses-tool", stack="qwen3-8b-awq@fake", case="case-1"
    )

    assert parts(events)[-1][0] == "final_result"
    assert parts(events)[-1][1].startswith('{"diagnoses": ["fake diagnoses 1"')
    assert of(events, "validity")[0]["valid"] is True


def test_an_llm_still_calling_tools_is_stopped(
    run: Run, through: Callable[[Any], None]
):
    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        return streaming(body | {"messages": body["messages"][:1]})

    through(httpx2.MockTransport(handler))

    events = run(configuration="test-tools", stack="qwen3-8b-awq@fake", case="case-1")

    assert of(events, "error")[0]["message"] == (
        "stopped: still calling tools after 5 rounds"
    )
    assert recorded(events)["status"] == "completed"


def test_a_tool_with_nothing_to_run_is_said_before_anything_is_sent(
    alex: Client, fake: FakeTransport
):
    _ = ToolBranchModel.objects.filter(name="sentinel_op").update(details={})

    response = post(
        alex, configuration="test-tools", stack="qwen3-8b-awq@fake", case="case-1"
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "the tool 'sentinel_op' has nothing to run"
    assert fake.requests == []


def test_runs_are_listed_the_latest_first(alex: Client, run: Run):
    _ = run(**FREE_TEXT, case="case-1", seed="none")
    _ = run(configuration="plan", stack="qwen3-8b-awq@fake", case="case-2", seed=3)

    listed = alex.get("/api/runs").json()

    assert [row["description"] for row in listed] == [
        "plan × qwen3-8b-awq@fake × case-2 (seed 3)",
        "free-text × qwen3-8b-awq@fake × case-1",
    ]
    assert [(score["scorer"], score["value"]) for score in listed[0]["scores"]] == [
        ("reciprocal_rank", 0.0)
    ]
    assert [(score["scorer"], score["value"]) for score in listed[1]["scores"]] == [
        ("first_mention", 17.0),
        ("reciprocal_rank", 0.5),
    ]
    assert len(alex.get("/api/runs", {"limit": 1}).json()) == 1
    assert alex.get("/api/runs", {"offset": 1}).json() == listed[1:]


def test_a_run_is_had_by_the_start_of_its_id(alex: Client, run: Run):
    run_ = recorded(run(**FREE_TEXT, case="case-1"))

    shown = alex.get(f"/api/runs/{run_['id'][:8]}")

    assert shown.status_code == 200
    assert shown.json() == run_
    assert alex.get("/api/runs/zzzz").json() == {"detail": "alex has no run 'zzzz'"}
    assert alex.get("/api/runs/zzzz").status_code == 404


def test_the_transcript_is_the_run_again_as_it_streamed(alex: Client, run: Run):
    live = run(configuration="test-tools", stack="qwen3-8b-awq@fake", case="case-1")
    again = alex.get(f"/api/runs/{live[0]['run']}/transcript").json()

    assert again[0] == live[0]
    assert parts(again) == parts(live)
    assert of(again, "usage") == of(live, "usage")
    assert of(again, "views") == of(live, "views")
    assert of(again, "scores") == of(live, "scores")


def test_the_transcript_reads_a_structured_answer_again(alex: Client, run: Run):
    live = run(configuration="plan", stack="qwen3-8b-awq@fake", case="case-1")
    again = alex.get(f"/api/runs/{live[0]['run']}/transcript").json()

    assert of(again, "validity") == of(live, "validity")
    assert of(again, "views") == of(live, "views")


def test_the_transcript_of_a_run_whose_server_failed_says_why(
    alex: Client, run: Run, through: Callable[[Any], None]
):
    through(httpx2.MockTransport(failing))
    live = run(**FREE_TEXT, case="case-1")

    again = alex.get(f"/api/runs/{live[0]['run']}/transcript").json()

    assert "no such model" in of(again, "error")[0]["message"]
    assert of(again, "usage") == []


def test_a_run_s_conversation_and_exchange_are_as_they_were(alex: Client, run: Run):
    run_id = run(**FREE_TEXT, case="case-1")[0]["run"]

    messages = alex.get(f"/api/runs/{run_id}/messages").json()
    exchange = alex.get(f"/api/runs/{run_id}/exchange").json()

    assert [(message["role"], message["kind"]) for message in messages] == [
        ("user", "request"),
        ("assistant", "response"),
    ]
    assert messages[0]["payload"]["parts"][-1]["content"] == "case vignette 1"
    assert json.loads(exchange["requests"][0])["model"] == "Qwen/Qwen3-8B-AWQ"
    assert exchange["responses"][0].startswith("data: ")

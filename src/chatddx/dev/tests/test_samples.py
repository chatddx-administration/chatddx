"""
The sample runs, made as the worker makes any: each comes out as its script
says, written down and scored.
"""

from typing import Any

import pytest
from jsonschema.validators import validator_for

from chatddx.dev.samples import BROKEN_OFF, SAMPLES, Script, sample
from chatddx.history.models import MessageKind, MessageModel, RunModel

pytestmark = pytest.mark.django_db


def parts(run: RunModel, kind: str) -> list[dict[str, Any]]:
    """The run's message parts of a kind, in the order they came."""
    return [
        part
        for message in MessageModel.objects.filter(run_uuid=run.uuid).order_by("pk")
        for part in message.payload.get("parts", [])
        if part["part_kind"] == kind
    ]


def returned(run: RunModel) -> list[str]:
    return [str(part["content"]) for part in parts(run, "tool-return")]


def test_the_typical_sample_thinks_once_answers_and_is_scored():
    run = sample("alice", "typical", case="case-1")

    assert (run.status, run.valid, run.error) == ("completed", True, None)
    assert len(parts(run, "thinking")) == 1
    answer: Any = run.answer
    assert answer["diagnoses"][0]["diagnosis"] == "Biliary colic"
    assert {score.scorer_name for score in run.scores.all()} == {
        "reciprocal_rank",
        "warning_mentions",
        "disposition_mentions",
    }


def test_the_broken_sample_went_wrong_every_way_and_broke_off():
    run = sample("alice", "broken", case="case-1")
    [error] = MessageModel.objects.filter(run_uuid=run.uuid, kind=MessageKind.ERROR)

    assert (run.status, run.answer) == ("errored", None)
    assert run.error == error.payload["error"] == f"RemoteProtocolError: {BROKEN_OFF}"
    failed, misnamed = returned(run)
    assert failed.startswith("HTTPStatusError: Server error '503 Service Unavailable'")
    assert misnamed == "invalid arguments: $: 'query' is a required property"
    # what it got out before the server went away
    assert parts(run, "text")[-1]["content"].endswith("masks peritonism, and")
    assert not run.scores.exists()


def test_the_rich_sample_holds_all_a_run_can():
    run = sample("alice", "rich", case="case-1")
    calls = [part["tool_name"] for part in parts(run, "tool-call")]
    got = returned(run)

    assert (run.status, run.valid) == ("completed", True)
    assert len(parts(run, "thinking")) == 5
    assert len(parts(run, "text")) == 2
    assert calls == ["web_search"] * 6 + ["final_result"]
    assert got[0].startswith("1. Pulmonary embolism in unexplained exacerbations")
    assert "invalid arguments: $.max_results: 'five' is not of type 'integer'" in got
    assert any(result.startswith("No results found for") for result in got)
    answer: Any = run.answer
    assert answer["diagnoses"][1]["diagnosis"] == "Pulmonary embolism"


@pytest.mark.parametrize("name", SAMPLES)
def test_what_a_sample_answers_holds_to_its_output_s_schema(name: str):
    run = sample("alice", name, case="case-1")
    schema: Any = run.trial.configuration.output.answer_schema
    script = Script.of(name)

    assert run.conversation is not None
    assert (run.conversation.description or "").startswith(script.configuration)

    if run.answer is not None:
        assert not list(validator_for(schema)(schema).iter_errors(run.answer))


def test_a_sample_wants_a_case_its_owner_has():
    with pytest.raises(ValueError, match="alice has no case 'nowhere'"):
        _ = sample("alice", "typical", case="nowhere")

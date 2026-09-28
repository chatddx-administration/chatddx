# pyright: basic
from typing import Any

import pytest
from django.test import Client

from chatddx.conftest import Recommit
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.reasoning.django import ReasoningBranchModel

pytestmark = pytest.mark.django_db

FREE_TEXT = {"configuration": "free-text", "stack": "qwen3-8b-awq@fake"}

PLAN = {"configuration": "plan", "stack": "qwen3-8b-awq@fake"}


def show(client: Client, **cell: Any) -> dict[str, Any]:
    response = client.get("/api/cell", cell)
    assert response.status_code == 200, response.content
    return response.json()


def save(client: Client, **cell: str) -> Any:
    return client.post("/api/cell/save", cell, content_type="application/json")


def held_to(cell: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["scorer"]: row for row in cell["scorers"]}


SLICES = {"instruction", "output", "coercion", "reasoning", "sampling", "toolset"}


def test_show_sets_each_variation_beside_what_it_resolves_to(alice: Client):
    cell = show(alice, **FREE_TEXT, reasoning="off")
    resolution = cell["resolution"]
    own = cell["configuration"]["trail"]

    assert cell["label"] == "free-text+reasoning=off"
    assert cell["configuration"]["owner"]["name"] == "archive"
    assert cell["stack"]["details"]["served_name"] == "Qwen/Qwen3-8B-AWQ"
    assert own["output"]["answer_schema"] is None
    assert set(own["output"]["views"]) == {"text", "differential"}
    assert (cell["set"]["reasoning"]["name"], own["reasoning"]["effort"]) == (
        "off",
        "default",
    )
    assert list(cell["set"]) == ["reasoning"]
    assert resolution["refusals"] == []
    assert resolution["reasoning"] == {
        "effort": "off",
        "intent": "off",
        "writes": {"chat_template_kwargs": {"enable_thinking": False}},
    }
    assert resolution["sampling"]["source"] == "recommended for 'off'"
    assert resolution["greedy"] is False
    assert resolution["coercion"] is None
    assert resolution["fields"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "‹case›" in resolution["user"]

    greedy = show(alice, **FREE_TEXT, sampling="greedy")["resolution"]

    assert greedy["greedy"] is True


def test_show_reports_a_refused_cell_slice_by_slice(alice: Client):
    cell = show(
        alice, configuration="plan-web", stack="gpt-oss-20b@fake", reasoning="off"
    )
    resolution = cell["resolution"]

    assert [
        (refusal["slice"], refusal["kind"]) for refusal in resolution["refusals"]
    ] == [("reasoning", "refused")]
    assert "always reasons" in resolution["refusals"][0]["reason"]
    assert resolution["coercion"]["mode"] == "native"
    assert [tool["name"] for tool in resolution["tools"]] == ["web_search"]
    assert (resolution["system"], resolution["user"], resolution["fields"]) == (
        None,
        None,
        None,
    )


def test_show_takes_half_a_cell_and_says_what_it_can_t_show(alice: Client):
    configured = show(alice, configuration="free-text")
    stacked = show(alice, stack="qwen3-8b-awq@fake")

    assert (configured["stack"], configured["resolution"]) == (None, None)
    assert SLICES <= set(configured["configuration"]["trail"])
    assert (stacked["configuration"], stacked["set"], stacked["scorers"]) == (
        None,
        {},
        None,
    )

    empty = alice.get("/api/cell")
    unset = alice.get("/api/cell", {"reasoning": "off"})
    nope = alice.get("/api/cell", {**FREE_TEXT, "reasoning": "nope"})
    none = alice.get("/api/cell", {**FREE_TEXT, "reasoning": "none"})
    blank = alice.get("/api/cell", {**FREE_TEXT, "reasoning": ""})

    assert (empty.status_code, unset.status_code) == (400, 400)
    assert "the cell is empty" in empty.json()["detail"]
    assert "no configuration to set its reasoning in" in unset.json()["detail"]
    assert (nope.status_code, nope.json()) == (
        404,
        {"detail": "no reasoning 'nope' for alice"},
    )
    assert blank.status_code == 422
    assert (none.status_code, none.json()["detail"]) == (
        400,
        "a configuration always has a reasoning: only a toolset can be none",
    )


def test_none_takes_the_toolset_out_and_the_own_variation_sets_nothing(alice: Client):
    out = show(
        alice, configuration="test-tools", stack="qwen3-8b-awq@fake", toolset="none"
    )
    own = show(alice, **FREE_TEXT, reasoning="default", toolset="none")

    assert out["label"] == "test-tools+toolset=none"
    assert out["set"] == {"toolset": None}
    assert out["configuration"]["trail"]["toolset"] is not None
    assert out["resolution"]["tools"] == []
    assert (own["label"], own["set"]) == ("free-text", {})


def test_show_says_which_cases_each_scorer_can_hold_the_cell_to(alice: Client):
    scorers = held_to(show(alice, **PLAN))
    one = show(alice, **PLAN, tag="tag-1")
    any_of = show(alice, **PLAN, tag=["tag-1", "nowhere"])
    nowhere = alice.get("/api/cell", {**PLAN, "tag": "nowhere"})

    assert scorers["reciprocal_rank"]["have"] == 2
    assert (
        scorers["warning_mentions"]["have"],
        scorers["warning_mentions"]["missing"],
    ) == (1, ["case-2"])
    assert (scorers["first_mention"]["offered"], scorers["first_mention"]["have"]) == (
        False,
        0,
    )
    assert (one["cases"], one["tags"]) == (1, ["tag-1"])
    assert held_to(one)["warning_mentions"]["missing"] == []
    assert any_of["cases"] == 1
    assert (nowhere.status_code, nowhere.json()) == (
        404,
        {"detail": "no case tagged nowhere for alice"},
    )


def test_show_names_the_cases_whose_pattern_doesn_t_parse(
    alice: Client, recommit: Recommit
):
    recommit(
        "case", "case-2", owner="alice", targets={"diagnosis": {"pattern": "fake & ("}}
    )

    scorers = held_to(show(alice, **PLAN))
    shown = alice.get("/api/registry/case/case-2").json()

    assert (
        scorers["reciprocal_rank"]["have"],
        scorers["reciprocal_rank"]["unread"],
    ) == (
        1,
        ["case-2"],
    )
    assert shown["branch"]["details"]["targets"]["diagnosis"]["pattern"] == "fake & ("
    assert list(shown["unread"]) == ["diagnosis"]


def test_show_part_shows_the_cell_s_own_or_says_it_has_none(alice: Client):
    output = alice.get("/api/cell/output", FREE_TEXT).json()
    reasoning = alice.get("/api/cell/reasoning", {**FREE_TEXT, "reasoning": "off"})
    llm = alice.get("/api/cell/llm", FREE_TEXT).json()
    toolset = alice.get("/api/cell/toolset", FREE_TEXT)
    case = alice.get("/api/cell/case", FREE_TEXT)
    stackless = alice.get("/api/cell/llm", {"configuration": "free-text"})

    assert (output["branch"]["name"], output["branch"]["owner"]["name"]) == (
        "free-text",
        "archive",
    )
    assert set(output["branch"]["trail"]["views"]) == {"text", "differential"}
    assert output["runs"] == {"runs": 0, "errored": 0, "scorers": []}
    assert reasoning.json()["branch"]["name"] == "off"
    assert llm["branch"]["name"] == "qwen3-8b-awq"
    assert (toolset.status_code, toolset.json()) == (
        404,
        {"detail": "the cell has no toolset"},
    )
    assert case.status_code == 404
    assert (stackless.status_code, stackless.json()) == (
        400,
        {"detail": "the cell has no stack"},
    )


def test_the_reasoning_table_sets_every_variation_on_every_stack(alice: Client):
    bare = alice.get("/api/reasoning").json()
    table = alice.get("/api/reasoning", {**FREE_TEXT, "reasoning": "high"}).json()
    names = [variation["name"] for variation in table["variations"]]
    stacks = {row["stack"]: row for row in table["stacks"]}
    gpt_oss = dict(zip(names, stacks["gpt-oss-20b@fake"]["realizations"], strict=True))
    fake = dict(zip(names, stacks["qwen3-8b-awq@fake"]["realizations"], strict=True))

    assert (bare["sampling"], bare["current"]) == (None, None)
    assert not any(stack["current"] for stack in bare["stacks"])
    assert table["sampling"]["defaults"] == "recommended"
    assert [row["stack"] for row in table["stacks"] if row["current"]] == [
        "qwen3-8b-awq@fake"
    ]
    assert [
        variation["name"]
        for variation in table["variations"]
        if variation["trail"]["fingerprint"] == table["current"]
    ] == ["high"]
    assert "always reasons" in gpt_oss["off"]["refusals"][0]["reason"]
    assert gpt_oss["high"]["reasoning"]["writes"] == {"reasoning_effort": "high"}
    assert fake["off"]["sampling"]["writes"]["temperature"] == 0.7


def test_scorers_say_what_each_reads_and_what_the_cell_offers(alice: Client):
    bare = alice.get("/api/scorers").json()
    offered = {
        scorer["name"]: scorer["offered"]
        for scorer in alice.get("/api/scorers", FREE_TEXT).json()
    }

    assert [scorer["name"] for scorer in bare] == [
        "disposition_mentions",
        "first_mention",
        "reciprocal_rank",
        "warning_mentions",
    ]
    assert all(scorer["offered"] is None for scorer in bare)
    assert offered == {
        "disposition_mentions": False,
        "first_mention": True,
        "reciprocal_rank": True,
        "warning_mentions": False,
    }


def test_save_keeps_the_cell_as_a_configuration_of_one_s_own(alice: Client):
    saved = save(alice, configuration="free-text", reasoning="off", name="quiet")

    assert saved.status_code == 200, saved.content
    assert saved.json()["what"] == "created"
    assert saved.json()["configuration"]["owner"]["name"] == "alice"

    quiet = ConfigurationBranchModel.objects.get(owner__name="alice", name="quiet")
    off = ReasoningBranchModel.objects.get(owner__name="archive", name="off")

    assert quiet.trail.reasoning_id == off.trail_id
    assert show(alice, configuration="quiet")["label"] == "quiet"

    nothing = save(alice, name="nothing")
    slashed = save(alice, configuration="free-text", name="bob/mine")

    assert (nothing.status_code, slashed.status_code) == (400, 400)
    assert "no configuration to save" in nothing.json()["detail"]
    assert "a name can't hold '/'" in slashed.json()["detail"]

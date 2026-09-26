# pyright: basic
from typing import Any

import pytest
from django.test import Client

from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import CaseBranchDetails, Expected
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.reasoning.django import ReasoningBranchModel
from chatddx.repo.store.branch import commit

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


def slice_of(cell: dict[str, Any], entity: str) -> dict[str, Any]:
    return next(row for row in cell["slices"] if row["slice"] == entity)


def test_show_sets_each_variation_beside_what_it_resolves_to(alex: Client):
    cell = show(alex, **FREE_TEXT, reasoning="off")
    resolution = cell["resolution"]
    reasoning = slice_of(cell, "reasoning")

    assert cell["label"] == "free-text+reasoning=off"
    assert cell["stack"]["served_name"] == "Qwen/Qwen3-8B-AWQ"
    assert cell["output"] == {"free_text": True, "views": ["text", "differential"]}
    assert (reasoning["variation"]["name"], reasoning["own"]["name"]) == (
        "off",
        "default",
    )
    assert reasoning["set"] is True
    assert resolution["resolved"] is True
    assert resolution["reasoning"] == {
        "effort": "off",
        "intent": "off",
        "writes": {"chat_template_kwargs": {"enable_thinking": False}},
    }
    assert resolution["sampling"]["source"] == "recommended for 'off'"
    assert resolution["sampling"]["greedy"] is False
    assert resolution["coercion"] is None
    assert resolution["fields"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "‹case›" in resolution["user"]

    greedy = show(alex, **FREE_TEXT, sampling="greedy")["resolution"]["sampling"]

    assert greedy["greedy"] is True


def test_show_reports_a_refused_cell_slice_by_slice(alex: Client):
    cell = show(
        alex, configuration="plan-web", stack="gpt-oss-20b@fake", reasoning="off"
    )
    resolution = cell["resolution"]

    assert resolution["resolved"] is False
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


def test_show_takes_half_a_cell_and_says_what_it_can_t_show(alex: Client):
    configured = show(alex, configuration="free-text")
    stacked = show(alex, stack="qwen3-8b-awq@fake")

    assert (configured["stack"], configured["resolution"]) == (None, None)
    assert len(configured["slices"]) == 6
    assert (stacked["configuration"], stacked["slices"], stacked["scorers"]) == (
        None,
        [],
        None,
    )

    empty = alex.get("/api/cell")
    unset = alex.get("/api/cell", {"reasoning": "off"})
    nope = alex.get("/api/cell", {**FREE_TEXT, "reasoning": "nope"})
    none = alex.get("/api/cell", {**FREE_TEXT, "reasoning": "none"})
    blank = alex.get("/api/cell", {**FREE_TEXT, "reasoning": ""})

    assert (empty.status_code, unset.status_code) == (400, 400)
    assert "the cell is empty" in empty.json()["detail"]
    assert "no configuration to set its reasoning in" in unset.json()["detail"]
    assert (nope.status_code, nope.json()) == (
        404,
        {"detail": "no reasoning 'nope' for alex"},
    )
    assert blank.status_code == 422
    assert (none.status_code, none.json()["detail"]) == (
        400,
        "a configuration always has a reasoning: only a toolset can be none",
    )


def test_none_takes_the_toolset_out_and_the_own_variation_sets_nothing(alex: Client):
    out = show(
        alex, configuration="test-tools", stack="qwen3-8b-awq@fake", toolset="none"
    )
    toolset = slice_of(out, "toolset")
    own = show(alex, **FREE_TEXT, reasoning="default", toolset="none")

    assert out["label"] == "test-tools+toolset=none"
    assert (toolset["variation"], toolset["own"]["name"], toolset["set"]) == (
        None,
        "sentinel",
        True,
    )
    assert out["resolution"]["tools"] == []
    assert own["label"] == "free-text"
    assert not any(row["set"] for row in own["slices"])


def test_show_says_which_cases_each_scorer_can_hold_the_cell_to(alex: Client):
    scorers = held_to(show(alex, **PLAN))
    one = show(alex, **PLAN, tag="tag-1")
    any_of = show(alex, **PLAN, tag=["tag-1", "nowhere"])
    nowhere = alex.get("/api/cell", {**PLAN, "tag": "nowhere"})

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
        {"detail": "no case tagged nowhere for alex"},
    )


def test_show_names_the_cases_whose_pattern_doesn_t_parse(alex: Client):
    case = CaseBranchModel.objects.filter(owner__name="archive", name="case-2").latest(
        "pk"
    )
    _ = commit(
        case.trail,
        CaseBranchDetails(
            name="case-2",
            owner="alex",
            targets={"diagnosis": Expected(pattern="fake & (")},
        ),
    )

    scorers = held_to(show(alex, **PLAN))
    shown = alex.get("/api/registry/case/case-2").json()
    diagnosis = next(row for row in shown["targets"] if row["kind"] == "diagnosis")

    assert (
        scorers["reciprocal_rank"]["have"],
        scorers["reciprocal_rank"]["unread"],
    ) == (
        1,
        ["case-2"],
    )
    assert diagnosis["pattern"] == "fake & ("
    assert diagnosis["unread"] is not None


def test_show_part_shows_the_cell_s_own_or_says_it_has_none(alex: Client):
    output = alex.get("/api/cell/output", FREE_TEXT).json()
    reasoning = alex.get("/api/cell/reasoning", {**FREE_TEXT, "reasoning": "off"})
    llm = alex.get("/api/cell/llm", FREE_TEXT).json()
    toolset = alex.get("/api/cell/toolset", FREE_TEXT)
    case = alex.get("/api/cell/case", FREE_TEXT)
    stackless = alex.get("/api/cell/llm", {"configuration": "free-text"})

    assert (output["name"], output["owner"]) == ("free-text", "archive")
    assert list(output["trail"]["views"]) == ["text", "differential"]
    assert output["runs"] == {"runs": 0, "errored": 0, "scorers": []}
    assert reasoning.json()["name"] == "off"
    assert llm["name"] == "qwen3-8b-awq"
    assert (toolset.status_code, toolset.json()) == (
        404,
        {"detail": "the cell has no toolset"},
    )
    assert (case.status_code, case.json()) == (
        400,
        {"detail": "a case isn't in the cell"},
    )
    assert (stackless.status_code, stackless.json()) == (
        400,
        {"detail": "the cell has no stack"},
    )


def test_the_reasoning_table_sets_every_variation_on_every_stack(alex: Client):
    bare = alex.get("/api/reasoning").json()
    table = alex.get("/api/reasoning", {**FREE_TEXT, "reasoning": "high"}).json()
    stacks = {row["stack"]: row for row in table["stacks"]}
    gpt_oss = {
        row["variation"]: row for row in stacks["gpt-oss-20b@fake"]["realizations"]
    }
    fake = {
        row["variation"]: row for row in stacks["qwen3-8b-awq@fake"]["realizations"]
    }

    assert bare["sampling"] is None
    assert not any(stack["current"] for stack in bare["stacks"])
    assert table["sampling"]["name"] == "recommended"
    assert [row["stack"] for row in table["stacks"] if row["current"]] == [
        "qwen3-8b-awq@fake"
    ]
    assert [row["name"] for row in table["variations"] if row["current"]] == ["high"]
    assert "always reasons" in gpt_oss["off"]["refusals"][0]["reason"]
    assert gpt_oss["high"]["reasoning"]["writes"] == {"reasoning_effort": "high"}
    assert fake["off"]["sampling"]["writes"]["temperature"] == 0.7


def test_scorers_say_what_each_reads_and_what_the_cell_offers(alex: Client):
    bare = alex.get("/api/scorers").json()
    offered = {
        scorer["name"]: scorer["offered"]
        for scorer in alex.get("/api/scorers", FREE_TEXT).json()
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


def test_save_keeps_the_cell_as_a_configuration_of_one_s_own(alex: Client):
    saved = save(alex, configuration="free-text", reasoning="off", name="quiet")

    assert saved.status_code == 200, saved.content
    assert saved.json()["what"] == "created"
    assert saved.json()["configuration"]["owner"] == "alex"

    quiet = ConfigurationBranchModel.objects.get(owner__name="alex", name="quiet")
    off = ReasoningBranchModel.objects.get(owner__name="archive", name="off")

    assert quiet.trail.reasoning_id == off.trail_id
    assert show(alex, configuration="quiet")["label"] == "quiet"

    nothing = save(alex, name="nothing")
    slashed = save(alex, configuration="free-text", name="bob/mine")

    assert (nothing.status_code, slashed.status_code) == (400, 400)
    assert "no configuration to save" in nothing.json()["detail"]
    assert "a name can't hold '/'" in slashed.json()["detail"]

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

REASONING = [
    "default",
    "off",
    "on",
    "on-budget-2048",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
]


def show(client: Client, **cell: Any) -> dict[str, Any]:
    response = client.get("/api/cell", cell)
    assert response.status_code == 200, response.content
    return response.json()


def held_to(cell: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["scorer"]: row for row in cell["scorers"]}


def save(client: Client, **cell: str) -> Any:
    return client.post("/api/cell/save", cell, content_type="application/json")


def test_show_sets_each_variation_beside_what_it_resolves_to(alex: Client):
    cell = show(alex, **FREE_TEXT)
    resolution = cell["resolution"]

    assert cell["label"] == "free-text"
    assert cell["stack"]["served_name"] == "Qwen/Qwen3-8B-AWQ"
    assert cell["output"] == {"free_text": True, "views": ["text", "differential"]}
    assert resolution["resolved"] is True
    assert resolution["reasoning"] == {
        "effort": "default",
        "intent": "on",
        "writes": {"chat_template_kwargs": {"enable_thinking": True}},
    }
    assert resolution["sampling"]["source"] == "recommended for 'on'"
    assert resolution["coercion"] is None
    assert resolution["fields"]["chat_template_kwargs"] == {"enable_thinking": True}
    assert (
        "List the plausible diagnoses, one per line, most likely first."
        in resolution["slots"]["output_guidance"]
    )
    assert "‹case›" in resolution["user"]


def test_show_says_what_is_set_and_what_the_configuration_has(alex: Client):
    cell = show(alex, **FREE_TEXT, reasoning="off")
    reasoning = next(row for row in cell["slices"] if row["slice"] == "reasoning")

    assert cell["label"] == "free-text+reasoning=off"
    assert (reasoning["variation"]["name"], reasoning["own"]["name"]) == (
        "off",
        "default",
    )
    assert reasoning["set"] is True
    assert cell["resolution"]["reasoning"]["writes"] == {
        "chat_template_kwargs": {"enable_thinking": False}
    }
    assert cell["resolution"]["sampling"]["source"] == "recommended for 'off'"


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


def test_show_says_how_the_answer_is_held_and_what_the_facts_note(alex: Client):
    coercion = show(alex, configuration="diagnoses-tool", stack="gpt-oss-20b@fake")[
        "resolution"
    ]["coercion"]

    assert (coercion["requested"], coercion["mode"]) == ("tool", "tool")
    assert coercion["shown"] is False
    assert "vLLM ignores tool_choice = required for gpt-oss" in coercion["note"]
    assert coercion["sent"]["type"] == "object"


def test_show_shows_the_schema_where_the_coercion_shows_it(alex: Client):
    resolution = show(alex, configuration="plan-shown", stack="qwen3-8b-awq@fake")[
        "resolution"
    ]

    assert resolution["coercion"]["shown"] is True
    assert "Answer with a JSON object that matches this JSON Schema" in (
        resolution["system"] + resolution["user"]
    )


def test_show_takes_half_a_cell(alex: Client):
    configured = show(alex, configuration="free-text")
    stacked = show(alex, stack="qwen3-8b-awq@fake")

    assert (configured["stack"], configured["resolution"]) == (None, None)
    assert len(configured["slices"]) == 6
    assert (stacked["configuration"], stacked["slices"]) == (None, [])
    assert stacked["stack"]["llm"]["name"] == "qwen3-8b-awq"


def test_show_says_what_it_can_t_show(alex: Client):
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
    assert none.status_code == 400
    assert none.json()["detail"] == (
        "a configuration always has a reasoning: only a toolset can be none"
    )


def test_none_takes_the_toolset_out(alex: Client):
    out = show(
        alex, configuration="test-tools", stack="qwen3-8b-awq@fake", toolset="none"
    )
    toolset = next(row for row in out["slices"] if row["slice"] == "toolset")

    assert out["label"] == "test-tools+toolset=none"
    assert (toolset["variation"], toolset["own"]["name"], toolset["set"]) == (
        None,
        "sentinel",
        True,
    )
    assert out["resolution"]["tools"] == []


def test_setting_the_configuration_s_own_variation_sets_nothing(alex: Client):
    cell = show(alex, **FREE_TEXT, reasoning="default", toolset="none")

    assert cell["label"] == "free-text"
    assert not any(row["set"] for row in cell["slices"])


def test_the_reasoning_table_sets_every_variation_on_every_stack(alex: Client):
    table = alex.get("/api/reasoning").json()
    stacks = {row["stack"]: row for row in table["stacks"]}
    gpt_oss = {
        realized["variation"]: realized
        for realized in stacks["gpt-oss-20b@fake"]["realizations"]
    }
    pelle = {
        realized["variation"]: realized
        for realized in stacks["qwen3-8b-awq@pelle"]["realizations"]
    }

    assert [variation["name"] for variation in table["variations"]] == REASONING
    assert table["sampling"] is None
    assert "always reasons" in gpt_oss["off"]["refusals"][0]["reason"]
    assert gpt_oss["high"]["reasoning"]["writes"] == {"reasoning_effort": "high"}
    assert (
        "a budget needs a reasoning parser"
        in (pelle["on-budget-2048"]["refusals"][0]["reason"])
    )
    assert not any(stack["current"] for stack in table["stacks"])


def test_the_reasoning_table_pulls_in_the_cell_s_sampling(alex: Client):
    table = alex.get("/api/reasoning", {**FREE_TEXT, "reasoning": "high"}).json()
    current = [row["stack"] for row in table["stacks"] if row["current"]]
    fake = next(row for row in table["stacks"] if row["stack"] == "qwen3-8b-awq@fake")
    off = next(row for row in fake["realizations"] if row["variation"] == "off")

    assert table["sampling"]["name"] == "recommended"
    assert current == ["qwen3-8b-awq@fake"]
    assert [row["name"] for row in table["variations"] if row["current"]] == ["high"]
    assert off["sampling"]["writes"]["temperature"] == 0.7
    assert off["sampling"]["writes"]["top_p"] == 0.8


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
    assert {(scorer["view"], scorer["target_kind"]) for scorer in bare} >= {
        ("text", "diagnosis"),
        ("differential", "diagnosis"),
    }
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


def test_saving_again_is_a_new_version_or_nothing(alex: Client):
    whats = [
        save(alex, **cell, name="mine").json()["what"]
        for cell in (
            {"configuration": "free-text"},
            {"configuration": "free-text"},
            {"configuration": "free-text", "reasoning": "high"},
        )
    ]

    assert whats == ["created", "unchanged", "a new version"]
    assert ConfigurationBranchModel.objects.filter(owner__name="alex").count() == 2


def test_a_saved_configuration_keeps_what_its_tools_run(alex: Client):
    saved = save(alex, configuration="test-tools", name="my-tools").json()

    assert "tool sentinel_op" in saved["copied"]

    tool = alex.get("/api/registry/tool/sentinel_op").json()

    assert tool["owner"] == "alex"
    assert tool["details"]["implementation"] is not None


def test_save_says_what_it_can_t_save(alex: Client):
    nothing = save(alex, name="nothing")
    slashed = save(alex, configuration="free-text", name="bob/mine")

    assert (nothing.status_code, slashed.status_code) == (400, 400)
    assert "no configuration to save" in nothing.json()["detail"]
    assert "a name can't hold '/'" in slashed.json()["detail"]


def test_show_says_which_cases_each_scorer_can_hold_the_cell_to(alex: Client):
    cell = show(alex, **PLAN)
    scorers = held_to(cell)

    assert (cell["cases"], cell["tags"]) == (2, [])
    assert scorers["reciprocal_rank"]["have"] == 2
    assert scorers["warning_mentions"]["target_kind"] == "warning"
    assert (
        scorers["warning_mentions"]["have"],
        scorers["warning_mentions"]["missing"],
    ) == (1, ["case-2"])
    assert (scorers["first_mention"]["offered"], scorers["first_mention"]["have"]) == (
        False,
        0,
    )


def test_show_tag_counts_only_the_cases_with_any_of_the_tags(alex: Client):
    one = show(alex, **PLAN, tag="tag-1")
    any_of = show(alex, **PLAN, tag=["tag-1", "nowhere"])
    nowhere = alex.get("/api/cell", {**PLAN, "tag": "nowhere"})

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


def test_show_says_whether_sampling_is_greedy(alex: Client):
    recommended = show(alex, **FREE_TEXT)["resolution"]["sampling"]
    greedy = show(alex, **FREE_TEXT, sampling="greedy")["resolution"]["sampling"]

    assert (recommended["greedy"], greedy["greedy"]) == (False, True)
    assert greedy["writes"]["temperature"] == 0


def test_show_part_shows_the_cell_s_own(alex: Client):
    output = alex.get("/api/cell/output", FREE_TEXT).json()
    reasoning = alex.get("/api/cell/reasoning", {**FREE_TEXT, "reasoning": "off"})
    llm = alex.get("/api/cell/llm", FREE_TEXT).json()
    configuration = alex.get("/api/cell/configuration", FREE_TEXT).json()

    assert (output["name"], output["owner"]) == ("free-text", "archive")
    assert list(output["trail"]["views"]) == ["text", "differential"]
    assert output["runs"] == {"runs": 0, "errored": 0, "scorers": []}
    assert reasoning.json()["name"] == "off"
    assert llm["name"] == "qwen3-8b-awq"
    assert configuration["name"] == "free-text"


def test_show_part_says_what_the_cell_doesn_t_have(alex: Client):
    toolset = alex.get("/api/cell/toolset", FREE_TEXT)
    removed = alex.get(
        "/api/cell/toolset",
        {"configuration": "test-tools", "toolset": "none"},
    )
    case = alex.get("/api/cell/case", FREE_TEXT)
    stackless = alex.get("/api/cell/llm", {"configuration": "free-text"})

    assert (toolset.status_code, toolset.json()) == (
        404,
        {"detail": "the cell has no toolset"},
    )
    assert removed.status_code == 404
    assert (case.status_code, case.json()) == (
        400,
        {"detail": "a case isn't in the cell"},
    )
    assert (stackless.status_code, stackless.json()) == (
        400,
        {"detail": "the cell has no stack"},
    )

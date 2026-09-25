from collections.abc import Callable

import pytest

type Say = Callable[..., str]

pytestmark = pytest.mark.django_db

REASONING = (
    "default",
    "off",
    "on",
    "on-budget-2048",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
)


def row_names(table: str) -> list[str]:
    cells = [
        line.split("│")[1].strip()
        for line in table.splitlines()
        if line.startswith("│")
    ]
    return [cell for cell in cells if cell]


def test_show_sets_each_variation_beside_what_it_resolves_to(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "show")

    assert "cell: free-text × qwen3-8b-awq@fake" in written
    assert (
        "the LLM's default, 'on': chat_template_kwargs.enable_thinking=true" in written
    )
    assert "recommended for 'on'" in written
    assert "List the plausible diagnoses, one per line, most likely first." in written


def test_show_reports_a_refused_cell_slice_by_slice(say: Say):
    written = say("cell plan-web gpt-oss-20b@fake", "set reasoning off", "show")

    assert written.count("refused:") == 1
    assert "refused: always reasons" in written
    assert "response_format: guided decoding holds the answer" in written
    assert "offered: web_search" in written


def test_show_needs_something_in_the_cell(say: Say):
    assert "the cell is empty: use CONFIGURATION, on STACK" in say("show")


def test_show_says_what_is_set_and_what_the_configuration_has(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "set reasoning off", "show")

    assert "off (set; free-text has default)" in written
    assert "chat_template_kwargs.enable_thinking=false" in written
    assert "recommended for 'off'" in written


def test_show_says_which_tools_the_llm_is_offered(say: Say):
    written = say("cell plan-web qwen3-8b-awq@fake", "show")

    assert "offered: web_search" in written
    assert "You have access to a web_search tool." in written


def test_show_says_how_the_answer_is_held_and_what_the_facts_note(say: Say):
    written = say("cell diagnoses-tool gpt-oss-20b@fake", "show")

    assert "a final_result tool holds the answer to the schema" in written
    assert "the LLM reads it as the tool's parameters" in written
    assert "vLLM ignores tool_choice = required for gpt-oss" in written


def test_show_shows_a_schema_prompt_and_clips_a_long_one(say: Say):
    written = say("cell plan-shown qwen3-8b-awq@fake", "show")

    assert "the LLM reads it through schema_prompt" in written
    assert "Answer with a JSON object that matches this JSON Schema" in written
    assert "more lines" in written


def test_the_reasoning_table_sets_every_variation_on_every_stack(say: Say):
    written = say("reasoning")

    assert row_names(written) == list(REASONING)

    for stack in ("gpt-oss-20b@fake", "qwen3-8b-awq@pelle", "qwen3-8b-awq@fake"):
        assert written.count(stack) == 1

    assert "refused: always reasons" in written
    assert "thinking_token_budget=2048" in written
    assert "a budget needs a reasoning parser" in written
    assert "the cell has no configuration: no sampling is pulled in" in written


def test_the_reasoning_table_pulls_in_the_cell_s_sampling(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "set reasoning high", "reasoning")

    assert "▸ high" in written
    assert "▸ qwen3-8b-awq@fake" in written
    assert "sampling as 'recommended' pulls it in" in written
    assert "temperature=0.7 top_p=0.8" in written


def line_of(written: str, start: str) -> str:
    """The last line written that starts with `start`, spaces aside."""
    return [line for line in written.splitlines() if line.strip().startswith(start)][-1]


def test_show_case_says_its_text_and_its_targets(say: Say):
    written = say("show case case-1")

    assert "case case-1, archive's" in written
    assert "vignette" in line_of(written, "vignette")
    assert "case vignette 1" in written
    assert "Fake diagnosis B" in line_of(written, "targets.diagnosis.text")
    assert "fake & diagnosis & (b | 2)" in line_of(written, "targets.diagnosis.pattern")
    assert "missing" in line_of(written, "targets.disposition.text")
    assert "admit*" in line_of(written, "targets.disposition.pattern")
    assert "missing" in line_of(written, "targets.dont_miss")
    assert "tag-1 tag-2" in line_of(written, "tags")
    assert "no runs of yours with this case" in written


def test_show_case_counts_your_runs_by_scorer(say: Say):
    _ = say(
        "cell free-text qwen3-8b-awq@fake", "run case-1", "run case-1 7", "run case-2"
    )
    shown = say("show case case-1")

    assert "2 runs of yours with it" in shown
    assert line_of(shown, "reciprocal_rank").split()[:2] == ["reciprocal_rank", "2"]
    assert line_of(shown, "first_mention").split()[:2] == ["first_mention", "2"]


def test_show_an_entity_without_a_name_shows_the_cell_s(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "show output")

    assert "output free-text, archive's" in written
    assert "whole" in line_of(written, "views.text")
    assert "lines" in line_of(written, "views.differential")
    assert "no runs of yours with this output" in written


def test_show_names_what_a_stack_holds(say: Say):
    written = say("show stack qwen3-8b-awq@fake")

    assert "fake" in line_of(written, "machine")
    assert "qwen3-8b-awq" in line_of(written, "llm")
    assert "http://localhost:12099/v1/" in line_of(written, "endpoint")


def test_show_scorer_sums_up_the_runs_it_scored(say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "run case-1")
    shown = say("show scorer first_mention")

    assert "patterns:first_mention" in line_of(shown, "function")
    assert "1 run of yours with it" in shown
    assert line_of(shown, "first_mention").split()[:2] == ["first_mention", "1"]
    assert "reciprocal_rank" not in shown


def test_show_says_what_it_can_t_show(say: Say):
    assert "no entity 'frobnicate'" in say("show frobnicate")
    assert "a case isn't in the cell: show case NAME" in say("show case")
    assert "the cell has no configuration: show output NAME" in say("show output")
    assert "the cell has no toolset" in say(
        "cell free-text qwen3-8b-awq@fake", "show toolset"
    )


def test_show_writes_what_is_json_as_json(say: Say):
    written = say("show tool sentinel_op")

    assert '"additionalProperties": false' in written
    assert "sentinel_op:sentinel_op" in line_of(written, "implementation.function")


def test_show_case_says_missing_for_each_kind_it_has_no_target_of(say: Say):
    written = say("show case case-2")

    assert "nothing & listed" in line_of(written, "targets.diagnosis.pattern")

    for kind in ("warning", "disposition", "dont_miss"):
        assert line_of(written, f"targets.{kind}").split()[-1] == "missing"


def test_show_says_which_cases_each_scorer_can_hold_the_cell_to(say: Say):
    written = say("cell plan qwen3-8b-awq@fake", "show")

    assert "of 2 cases" in written
    assert "2 have it" in line_of(written, "reciprocal_rank")
    assert "1 have it; missing: case-2" in line_of(written, "warning_mentions")
    assert "the output offers no such view" in line_of(written, "first_mention")


def test_show_tag_counts_only_the_cases_with_any_of_the_tags(say: Say):
    written = say("cell plan qwen3-8b-awq@fake", "show tag tag-1")

    assert "of 1 case tagged tag-1" in written
    assert "1 have it" in line_of(written, "warning_mentions")
    assert "missing" not in line_of(written, "warning_mentions")


def test_show_tag_needs_a_tag_and_an_entity_one_name(say: Say):
    assert "usage: show tag TAG..." in say("show tag")
    assert "usage: show case [NAME]" in say("show case case-1 case-2")
    assert "no case tagged nowhere" in say(
        "cell plan qwen3-8b-awq@fake", "show tag nowhere"
    )

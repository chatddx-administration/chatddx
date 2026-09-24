"""What the cell is, and how it resolves on its stack, before anything is sent."""

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
    """A table's first column, where a row starts rather than wraps on."""
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
        "the model's default, 'on': chat_template_kwargs.enable_thinking=true"
        in written
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


def test_show_says_which_tools_the_model_is_offered(say: Say):
    written = say("cell plan-web qwen3-8b-awq@fake", "show")

    assert "offered: web_search" in written
    assert "You have access to a web_search tool." in written


def test_show_says_how_the_answer_is_held_and_what_the_facts_note(say: Say):
    written = say("cell diagnoses-tool gpt-oss-20b@fake", "show")

    assert "a final_result tool holds the answer to the schema" in written
    assert "the model reads it as the tool's parameters" in written
    assert "vLLM ignores tool_choice = required for gpt-oss" in written


def test_show_shows_a_schema_prompt_and_clips_a_long_one(say: Say):
    written = say("cell plan-shown qwen3-8b-awq@fake", "show")

    assert "the model reads it through schema_prompt" in written
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

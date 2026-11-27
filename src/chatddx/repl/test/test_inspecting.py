import pytest

from chatddx.bench import Bench
from chatddx.bench.test.helpers import another_expectation, owned
from chatddx.catalog import Entry, EntryField, Subject
from chatddx.inventory import Inventory
from chatddx.repl.test.helpers import (
    Say,
    by_hand,
    cells,
    line_of,
    pattern,
    row,
    tagged,
    targets_of,
)
from chatddx.store import Catalog
from chatddx.test.world import (
    CASES,
    GPT_OSS_ARTIFACT,
    LINES,
    LINES_GUIDED,
    MISTRAL_ARTIFACT,
    MISTRAL_MODEL,
    NATIVE,
    QWEN,
    QWEN_ARTIFACT,
    QWEN_BARE_ARTIFACT,
    QWEN_MODEL,
    TEST,
)

LEVELS = [
    "default",
    "off",
    "on",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "budget",
]
HANDLES = (QWEN_ARTIFACT, QWEN_BARE_ARTIFACT, GPT_OSS_ARTIFACT, MISTRAL_ARTIFACT)


def row_names(table: str) -> list[str]:
    cells = [
        line.split("│")[1].strip()
        for line in table.splitlines()
        if line.startswith("│")
    ]
    return [cell.removeprefix("▸ ") for cell in cells if cell]


def test_show_needs_a_configuration(say: Say):
    assert "the repl holds no configuration: use CONFIGURATION" in say("show")


@pytest.mark.slow
def test_show_sets_each_part_beside_what_it_is_and_renders_the_request(say: Say):
    written = say(f"use {LINES}", "show")
    sv = [id for id, case in CASES.items() if case.language == "sv"]

    assert f"variation: {LINES} × {QWEN_ARTIFACT}" in written
    assert f"{QWEN}  " in line_of(written, "endpoint")
    assert "recommended sampling, for reasoning on" in line_of(written, "sampling")
    assert '"temperature": 0.6' in written
    assert "text output" in line_of(written, "output")
    assert "List the plausible diagnoses, one per line, most likely first." in written
    assert "‹vignette›‹appendices›" in written
    assert '"seed": 7' in written
    assert f"en: {len(CASES) - len(sv)} cases, as written" in written
    assert f"sv: {len(sv)} cases, left out: lines has no translation into sv" in written
    assert "translations.missing" not in written
    assert "sv: 3 cases, translated" in say(f"use {LINES_GUIDED}", "show")


@pytest.mark.slow
def test_show_says_what_is_set_and_what_the_configuration_has(say: Say):
    written = say(f"use {LINES}", "set reasoning off", "show")

    assert f"off (set; {LINES} has —)" in written
    assert "reasoning off" in line_of(written, "reasoning")
    assert '"enable_thinking": false' in written


def test_show_says_what_the_lints_say_of_the_pair(say: Say):
    written = say("use native-tools", "show")

    assert "[warning] vllm.native_tools_uncallable" in written
    assert "with lookup, broken" in line_of(written, "toolset")


def test_show_leaves_the_output_s_schema_to_show_output(say: Say):
    written = say(f"use {NATIVE}", "show")

    assert "‹the output's schema›" in written
    assert "#/$defs/diagnosis" not in written
    assert "#/$defs/diagnosis" in say("show output")


@pytest.mark.slow
def test_show_says_the_seed_isn_t_sent_when_sampling_is_greedy(say: Say):
    written = say(f"use {LINES}", "set sampling greedy", "show")

    assert "greedy: the seed isn't sent" in written
    assert '"seed"' not in written


@pytest.mark.slow
def test_show_says_which_cases_each_scorer_can_hold_the_variation_to(say: Say):
    written = say(f"use {NATIVE}", "show")
    without = [id for id in CASES if "dont_miss" not in targets_of(id)]

    assert f"of {len(CASES)} cases" in written
    assert f"{len(CASES)} have it" in row(written, "answer", "differential")
    assert (
        f"{len(CASES) - len(without)} have it; missing: {' '.join(sorted(without))}"
        in row(written, "answer", "dont-miss")
    )

    written = say(f"use {LINES}", "show")

    assert "the output offers no such view" in row(written, "answer", "warning")
    assert f"{len(CASES)} have it" in row(written, "lines", "text")


@pytest.mark.slow
def test_show_tag_counts_only_the_cases_with_any_of_the_tags(say: Say):
    written = say(f"use {NATIVE}", "show tag targets")
    targets = tagged("targets")

    assert f"of {len(targets)} cases tagged targets" in written
    assert f"{len(targets)} have it" in row(written, "answer", "differential")

    written = say("show tag targets swedish")
    either = tagged("targets", "swedish")

    assert f"of {len(either)} cases tagged targets or swedish" in written


def test_show_tag_needs_a_tag_with_cases(say: Say):
    assert "usage: show tag TAG..." in say("show tag")
    assert "no case tagged nowhere for alice" in say(
        f"use {NATIVE}", "show tag nowhere"
    )


def test_show_case_says_its_vignette_expectation_and_tags(say: Say):
    written = say("show case noted")
    noted = CASES["noted"]
    vignette = (TEST / "vignettes" / "noted.txt").read_text().splitlines()[0]

    assert "case noted, archive's" in written
    assert "test/noted" in line_of(written, "source")
    assert vignette in line_of(written, "vignette")
    assert pattern("noted") in line_of(written, "expectation.diagnosis.pattern")
    assert line_of(written, "tags").split()[1:] == sorted(noted.tags)
    assert line_of(written, "language").split() == ["language", noted.language]
    assert '"author": "carol"' in written and '"author": "dave"' in written
    assert "no runs of yours with this case" in written


@pytest.mark.slow
def test_show_case_says_when_scoring_has_expectations_to_choose_from(
    bench: Bench, say: Say
):
    case = bench.family("noted").case
    _ = another_expectation(bench, case, {"diagnosis": {"pattern": "sepsis"}})
    written = say("show case noted")

    assert "has expectations to choose from" in line_of(written, "expectation")

    written = say(f"use {NATIVE}", "show tag targets")

    assert "to choose from: noted" in row(written, "answer", "differential")


def test_show_case_says_when_none_of_the_expectations_is_yours(bench: Bench, say: Say):
    case = bench.family("noted").case
    [schema] = bench.expectation_schemas(case)
    catalog, person = Catalog(bench.conn), bench.person.id
    [mine] = owned(bench, case, schema)
    catalog.note(Subject(thread=mine), Entry(field=EntryField.DELETED), person)
    written = say("show case noted")

    assert "none of yours" in line_of(written, "expectation")


def test_show_without_a_name_shows_the_variation_s(say: Say):
    written = say(f"use {LINES}", "show output")

    assert "output lines  " in written
    assert "List the plausible diagnoses" in line_of(written, "guidance")
    assert "no runs of yours with this output" in written

    written = say("show engine", "show model", "show endpoint")

    assert "chatddx fake-vllm" in line_of(written, "runtime.closure")
    assert QWEN_MODEL in line_of(written, "repo")
    assert line_of(written, "cleared for").split()[2:] == ["test", "typed"]


def test_show_configuration_says_when_the_variation_is_unsaved(say: Say):
    written = say(f"use {LINES}", "set reasoning off", "show configuration")

    assert f"configuration {LINES}+reasoning=off, unsaved" in written
    assert "enable_thinking" in written


def test_show_writes_what_is_json_as_json(say: Say):
    written = say("show tool lookup")

    assert '"additionalProperties": false' in written
    assert "chatddx.runner.test.tools:lookup" in line_of(written, "entry_point")

    written = say("show scorer judged")

    assert '"judge": "verdict"' in written and '"judge": "graded"' in written
    assert "sha256:" not in written


def test_show_says_what_it_can_t_show(say: Say):
    assert "no kind 'frobnicate'" in say("show frobnicate")
    assert "the repl holds no case: show case NAME" in say("show case")
    assert "no case 'nope' for alice" in say("show case nope")
    assert "the repl holds no configuration: show output NAME" in say("show output")
    assert "the repl holds no configuration: show engine NAME" in say("show engine")
    assert "the repl holds no scorer: show scorer NAME" in say("show scorer")
    assert f"{LINES} has no reasoning" in say(f"use {LINES}", "show reasoning")


def test_show_says_why_a_variation_can_t_run_and_has_no_lints_then(
    bench: Bench, say: Say
):
    by_hand(bench)
    written = say("use by hand", "show", "show engine")

    assert "by hand names no model: name the one to run it under" in written
    assert ["lints"] not in cells(written)
    assert "‹model›" in written

    written = say(f"under {QWEN_ARTIFACT}", "show")

    assert f"variation: by hand × {QWEN_ARTIFACT}" in written
    assert ["lints"] in cells(written)


def test_show_endpoint_says_when_its_engine_isn_t_stored(
    bench: Bench, world: Inventory, say: Say
):
    ghost = world.endpoints[QWEN].model_copy(update={"engine": "sha256:" + "0" * 64})
    bench.inventory = world.model_copy(
        update={"endpoints": {**world.endpoints, "ghost@nowhere": ghost}}
    )
    written = say("show endpoint ghost@nowhere", f"use {LINES}")

    assert (
        "endpoint 'ghost@nowhere' serves engine 000000, which isn't in the store"
        in written
    )
    assert f"variation: {LINES} × {QWEN_ARTIFACT}" in written


def test_the_reasoning_table_sets_every_level_on_every_model(say: Say):
    written = say("reasoning")

    assert row_names(written) == LEVELS
    for handle in HANDLES:
        assert written.count(f"┃ {handle} ") == 1
    assert "its nearest: always reasons" in written
    assert f"refused: {MISTRAL_MODEL} doesn't reason" in written
    assert "thinking_token_budget=N" in written
    assert "no configuration in use asks for a level" in written


def test_the_reasoning_table_marks_the_variation_s_level_and_handle(say: Say):
    written = say(f"use {LINES}", "reasoning")

    assert "│ ▸ default" in written
    assert f"┃ ▸ {QWEN_ARTIFACT} " in written

    written = say("set reasoning off", "reasoning")

    assert "│ ▸ off" in written
    assert "│ ▸ default" not in written


def test_scorers_say_whether_the_variation_s_output_offers_each_view(say: Say):
    written = say("scorers")

    assert "reciprocal_rank" in row(written, "answer")
    assert "$.diagnoses[?@.critical == true].diagnosis" in written
    assert "verdict, judged by verdict" in row(written, "note-comment")
    assert "points, judged by graded" in row(written, "note-graded")

    written = say(f"use {LINES}", "scorers")

    assert "doesn't offer it" in row(written, "answer")
    assert "offers it" in row(written, "lines")
    assert "the whole answer, lines@1" in written


def test_show_case_lists_a_family_s_appendices_and_the_cases_that_send_them(say: Say):
    written = say("show case whitespace")

    assert "labs" in line_of(written, "appendices")
    assert [
        "cases",
        "whitespace",
        "with",
        "labs",
        "its",
        "own",
        "expectation",
    ] in cells(written)

    written = say("show case whitespace with labs")

    assert written.startswith("case whitespace with labs")
    assert "CRP 180 mg/L, leukocytes 16." in line_of(written, "appendix labs")
    assert "appendicitis & perforat*" in written
    assert "cases" not in written.split("expectation")[0]
    assert "no runs of yours with this case" in written

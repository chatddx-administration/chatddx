import re
import signal
from collections.abc import Callable

import pytest

from chatddx.bench import Bench
from chatddx.catalog.titles import display_count
from chatddx.factors.base import Finding, resolve
from chatddx.factors.trial import Trial
from chatddx.fake_vllm.served import Served
from chatddx.fake_vllm.server import serving
from chatddx.inventory import Inventory, start_up
from chatddx.ledger import Run
from chatddx.repl.render import Tally, Transcript
from chatddx.repl.running import WRITING
from chatddx.repl.shell import SEEDS, Repl
from chatddx.repl.test.helpers import Say, by_hand, cells, tagged
from chatddx.runner import Grading, Halt, RunEvent, Running, ScoreEvent, Streamed
from chatddx.store import Store
from chatddx.test.world import (
    CASES,
    GPT_OSS,
    GPT_OSS_ARTIFACT,
    LINES,
    LINES_GUIDED,
    NATIVE,
    QWEN,
    QWEN_ARTIFACT,
    TOOL_ANSWER,
)


def test_seed_draws_a_short_seed_or_holds_one(repl: Repl, say: Say):
    written = say("seed")

    assert 0 <= repl.seed < SEEDS
    assert f"seed: #{repl.seed}" in written

    _ = say("seed 2147483647")
    assert repl.prompt == "alice #2147483647> "


def test_seed_says_what_isn_t_a_seed(repl: Repl, say: Say):
    written = say("seed -1", "seed 2147483648", "seed none")

    assert written.count("a seed is a whole number from 0 to 2147483647") == 3
    assert repl.seed == 7


def test_seed_says_a_greedy_configuration_isn_t_sent_it(say: Say):
    assert "greedy" not in say(f"use {LINES}", "seed 1")
    assert "greedy: the seed isn't sent" in say("set sampling greedy", "seed 2")


def ran(bench: Bench) -> list[Run]:
    return [Store(bench.conn).run(r.run) for r in bench.runs()]


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_run_streams_a_run_of_the_variation_and_scores_it(bench: Bench, say: Say):
    written = say(f"use {LINES}", "run noted")

    assert f"trial: {LINES} × {QWEN_ARTIFACT} × noted (seed 7)" in written
    assert "[thinking] I am the fake vLLM" in written
    assert re.search(
        r"Fake diagnosis \w\nFake diagnosis \w\nFake diagnosis \w", written
    )
    assert re.search(r"\(\d+ in, \d+ out\)", written)
    assert re.search(r"differential\n  1\. Fake diagnosis \w\n  2\.", written)
    assert "valid" not in written
    assert "scores" in written
    assert ["differential", "0", "not", "listed"] in cells(written)
    assert "recorded as run 1 of trial" in written

    [run] = ran(bench)
    assert run.finished is not None
    assert run.started.endpoint is not None and run.started.endpoint.name == QWEN
    assert [s.score for s in Store(bench.conn).scores_of(run.started.run)]


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_each_run_is_recorded_as_a_run_of_its_trial(bench: Bench, say: Say):
    written = say(f"use {LINES}", "run noted", "run noted")

    first, again = re.findall(r"recorded as run (\d+) of trial (\w{6})", written)

    assert (first[0], again[0]) == ("1", "2")
    assert first[1] == again[1]
    assert len({r.started.trial for r in ran(bench)}) == 1


def test_run_needs_a_configuration_whose_handle_is_served_here(
    bench: Bench, world: Inventory, say: Say
):
    assert "the repl holds no configuration" in say("run noted")

    endpoints = {n: e for n, e in world.endpoints.items() if n != QWEN}
    bench.inventory = world.model_copy(update={"endpoints": endpoints})
    written = say(f"use {LINES}", "run noted")
    assert f"no endpoint here serves model {QWEN_ARTIFACT}: pick another" in written
    assert ran(bench) == []


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_run_takes_a_seed_of_its_own(repl: Repl, bench: Bench, say: Say):
    written = say(f"use {LINES}", "run noted 42", "run noted x")

    assert "× noted (seed 42)" in written
    assert "a seed is a whole number from 0 to 2147483647, not x" in written
    assert repl.seed == 7

    [run] = ran(bench)
    assert resolve(bench.store.get, run.started.trial, Trial).seeds == (42,)


@pytest.mark.usefixtures("fake")
def test_a_structured_answer_is_checked_and_its_views_read(say: Say):
    written = say(f"use {NATIVE}", "run crlf")

    assert "\nvalid\n" in written
    assert (
        "differential\n  1. fake diagnosis 1\nwarning\n  1. fake acute warning\n"
        + "disposition\n  1. fake disposition\ndont-miss\n  nothing\n"
    ) in written
    assert "differential (list)" not in written and '{"diagnosis"' not in cells(written)
    assert ["warning", "0", "not", "named"] in cells(written)


@pytest.mark.usefixtures("fake")
def test_a_tool_contract_shows_the_call_the_answer_is_given_through(say: Say):
    written = say(f"use {TOOL_ANSWER}", "run bom")

    assert '[final_result] {"diagnoses": ["fake diagnoses 1"' in written
    assert "\nvalid\n" in written


@pytest.mark.usefixtures("fake")
def test_run_is_refused_where_the_gate_refuses(bench: Bench, say: Say):
    written = say("use native-tools", "run bom")

    assert "refused: the configuration's tools would get content from source test" in (
        written
    )
    assert "trial:" not in written
    assert ran(bench) == []


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_hand_written_configuration_runs_under_the_handle_named(
    bench: Bench, say: Say
):
    by_hand(bench)
    written = say("use by hand", "run noted")

    assert "by hand names no model: name the one to run it under" in written
    assert ran(bench) == []

    written = say(f"under {QWEN_ARTIFACT}", "run noted")

    assert f"trial: by hand × {QWEN_ARTIFACT} × noted (seed 7)" in written
    [run] = ran(bench)
    assert run.started.endpoint is not None and run.started.endpoint.name == QWEN


def test_run_is_refused_an_endpoint_that_doesn_t_answer(bench: Bench, say: Say):
    written = say(f"use {NATIVE}", f"set model {GPT_OSS_ARTIFACT}", "run bom")

    assert f"refused: endpoint '{GPT_OSS}' can't be confirmed" in written
    assert ran(bench) == []


@pytest.mark.slow
def test_a_run_that_runs_away_is_cut_short_and_what_came_scored(
    world: Inventory, bench: Bench, say: Say
):
    startup = start_up(world, bench.store.get, QWEN)
    with serving([Served.of(startup.argv[0], startup.argv[1:])], runaway=True):
        written = say(f"use {LINES}", "run noted")

    assert "stopped: nothing but whitespace for 100 tokens" in written
    assert re.search(r"differential\n  1\. Fake diagnosis \w", written)
    assert "recorded as run 1 of trial" in written

    [run] = ran(bench)
    [item] = run.items
    assert item.call.error == "stopped: nothing but whitespace for 100 tokens"


@pytest.mark.slow
def test_a_structured_answer_cut_short_is_salvaged(
    world: Inventory, bench: Bench, say: Say
):
    startup = start_up(world, bench.store.get, QWEN)
    with serving([Served.of(startup.argv[0], startup.argv[1:])], runaway=True):
        written = say(f"use {NATIVE}", "run bom")

    assert "stopped: nothing but whitespace for 100 tokens" in written
    assert "salvaged: cut short, and read with its structure closed" in written
    assert re.search(r"\(\d+ out\)", written)
    assert "no answer" not in written
    assert "answer.salvaged" not in written


@pytest.mark.slow
def test_run_tag_says_each_finding_once_with_how_often_it_came(
    world: Inventory, bench: Bench, say: Say
):
    startup = start_up(world, bench.store.get, QWEN)
    with serving([Served.of(startup.argv[0], startup.argv[1:])], runaway=True):
        written = say(f"use {NATIVE}", "run tag targets")
    targets = tagged("targets")

    stop = "stopped: nothing but whitespace for 100 tokens"
    assert f"[warning] call.failed: {stop} (×{len(targets)})" in written
    assert written.count("call.failed") == 1
    assert (
        "[info] answer.salvaged: cut short, and read with its structure closed; the "
        + f"call ended with: {stop} (×{len(targets)})"
    ) in written
    salvaged = [c for c in cells(written) if c[2:3] == ["salvaged"]]
    assert sorted(c[0] for c in salvaged) == targets
    assert all(int(c[1]) > 0 for c in salvaged)


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_greedy_variation_runs_without_its_seed(say: Say):
    written = say(f"use {LINES}", "set sampling greedy", "run noted")

    assert "greedy: the seed isn't sent" in written
    assert "recorded as run 1 of trial" in written
    assert "seed=7" not in written


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_run_tag_runs_the_variation_on_each_case_tagged_a_line_to_each(
    bench: Bench, say: Say
):
    written = say(f"use {LINES}", "run tag targets")
    targets = tagged("targets")

    assert (
        f"trial: {LINES} × {QWEN_ARTIFACT} × {len(targets)} cases tagged targets "
        + "(seed 7)"
        in written
    )
    assert ["case", "tokens", "outcome"] in cells(written)
    assert sorted(c[0] for c in cells(written) if c[2:] == ["completed"]) == targets
    assert "stopped after" not in written

    [run] = ran(bench)
    assert len(run.items) == len(targets)
    assert "recorded as run 1 of trial" in written
    assert ["lines", "text", "1", "@0", "0", str(len(targets) - 1)] in cells(written)


def test_run_tag_says_what_it_can_t_run(say: Say):
    assert "the repl holds no configuration" in say("run tag targets")
    assert "usage: run tag TAG..." in say(f"use {LINES}", "run tag")
    assert "no case tagged nowhere for alice" in say("run tag nowhere")


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_run_tag_runs_the_cases_with_any_of_its_tags(bench: Bench, say: Say):
    written = say(f"use {LINES}", "run tag targets nowhere swedish")
    either = tagged("targets", "swedish")
    swedish = [name for name in either if CASES[name].language == "sv"]
    english = len(either) - len(swedish)

    assert f"{english} cases tagged targets or nowhere or swedish (seed 7)" in written
    assert (
        f"left out: {len(swedish)} cases in sv, as lines has no translations into sv"
    ) in written
    [run] = ran(bench)
    assert len(run.items) == english


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_run_tag_over_several_languages_runs_each(bench: Bench, say: Say):
    written = say(f"use {LINES_GUIDED}", "run tag swedish")
    swedish = [name for name in tagged("swedish") if CASES[name].language == "sv"]
    english = len(tagged("swedish")) - len(swedish)

    assert f"{display_count(english, 'case')} tagged swedish, in en (seed 7)" in written
    assert f"{len(swedish)} cases tagged swedish, in sv, translated (seed 7)" in written
    assert "left out" not in written
    assert sorted(len(r.items) for r in ran(bench)) == sorted([english, len(swedish)])


def pressing(say: Say, *lines: str) -> str:
    try:
        return say(*lines)
    finally:
        assert signal.getsignal(signal.SIGINT) is signal.default_int_handler


def press_at(monkeypatch: pytest.MonkeyPatch, at: int, presses: int = 1) -> None:
    pressed = False
    count = Tally.count
    event = Transcript.event

    def press(tokens: int) -> None:
        nonlocal pressed
        if tokens >= at and not pressed:
            pressed = True
            for _ in range(presses):
                signal.raise_signal(signal.SIGINT)

    def counted(self: Tally, tokens: int) -> None:
        count(self, tokens)
        press(tokens)

    def evented(self: Transcript, e: RunEvent) -> None:
        event(self, e)
        if isinstance(e, Streamed):
            press(e.delta.tokens)

    monkeypatch.setattr(Tally, "count", counted)
    monkeypatch.setattr(Transcript, "event", evented)


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_ctrl_c_stops_a_run_as_it_streams_and_it_is_recorded_as_stopped(
    bench: Bench, say: Say, monkeypatch: pytest.MonkeyPatch
):
    press_at(monkeypatch, 5)
    written = pressing(say, f"use {LINES}", "run noted")

    assert "[thinking] I am the fake" in written
    assert "(stopped)" in written
    assert "recorded as run 1 of trial" in written

    [run] = ran(bench)
    [item] = run.items
    assert item.call.error == "stopped"
    assert run.finished is not None


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_ctrl_c_lets_the_case_under_way_finish_then_stops_the_run(
    bench: Bench, say: Say, monkeypatch: pytest.MonkeyPatch
):
    press_at(monkeypatch, 5)
    written = pressing(say, f"use {LINES}", "run tag targets")

    [run] = ran(bench)
    [item] = run.items
    assert item.call.error is None
    assert f"stopped after 1 of {len(tagged('targets'))} cases" in written
    assert "completed" in written
    assert run.finished is not None


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_ctrl_c_again_stops_the_case_under_way_too(
    bench: Bench, say: Say, monkeypatch: pytest.MonkeyPatch
):
    press_at(monkeypatch, 5, presses=2)
    written = pressing(say, f"use {LINES}", "run tag targets")
    targets = tagged("targets")

    [run] = ran(bench)
    [item] = run.items
    assert item.call.error == "stopped"
    assert f"stopped after 0 of {len(targets)} cases" not in written
    [_] = [c for c in cells(written) if c[2:] == ["stopped"] and c[0] in targets]
    assert f"stopped after 1 of {len(targets)} cases" in written
    assert "call.failed: stopped" in written


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_ctrl_c_twice_while_scoring_finishes_the_score_and_leaves_the_rest(
    bench: Bench, say: Say, monkeypatch: pytest.MonkeyPatch
):
    send = Grading.send

    def pressed(
        self: Grading,
        on_event: Callable[[ScoreEvent], None] | None = None,
        halt: Halt | None = None,
    ):
        signal.raise_signal(signal.SIGINT)
        signal.raise_signal(signal.SIGINT)
        send(self, on_event, halt)

    monkeypatch.setattr(Grading, "send", pressed)
    written = pressing(say, f"use {LINES}", "run noted")

    assert WRITING in written
    assert "not scored: stopped" in written
    assert "score.incomplete" in written
    assert "scoring stopped: score scores what is left" in written
    assert "recorded as run 1 of trial" in written

    store = Store(bench.conn)
    [run] = ran(bench)
    [given] = store.scores_of(run.started.run)
    assert store.score(given.score).finished is not None
    started = bench.run(run.started.run)
    assert len(bench.unscored(started)) == len(bench.scorers(started))

    monkeypatch.undo()
    assert "nothing to score" not in say("score")
    assert bench.unscored(started) == []


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_ctrl_c_waits_for_a_run_to_be_written_down_and_scored(
    bench: Bench, say: Say, monkeypatch: pytest.MonkeyPatch
):
    finish = Running.finish

    def pressed(self: Running) -> list[Finding]:
        signal.raise_signal(signal.SIGINT)
        return finish(self)

    monkeypatch.setattr(Running, "finish", pressed)
    written = pressing(say, f"use {LINES}", "run noted")

    assert "recorded as run 1 of trial" in written
    [run] = ran(bench)
    assert run.finished is not None
    assert Store(bench.conn).scores_of(run.started.run)


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_a_run_says_each_judge_call_as_it_goes_then_what_the_judges_said(say: Say):
    written = say(f"use {LINES}", "run noted")

    judging = [
        line.split() for line in written.splitlines() if line.startswith("judging")
    ]
    assert [(w[1], w[2], w[4], w[6], w[-2:]) for w in judging] == [
        ("noted:", "note-comment", "verdict,", "1", ["meets", "true"]),
        ("noted:", "note-answer", "verdict,", "1", ["meets", "true"]),
        ("noted:", "note-graded", "graded,", "1", ["points", "0"]),
        ("noted:", "note-graded", "graded,", "2", ["points", "1"]),
        ("noted:", "note-graded", "graded,", "3", ["points", "2"]),
    ]
    judged = written[written.index("\njudged\n") :]
    assert [
        "note-comment",
        "verdict,",
        "seed",
        "1",
        "meets",
        "true",
        "fake",
        "why",
    ] in (cells(judged))
    assert ["graded,", "seed", "3", "points", "2", "fake", "why"] in cells(judged)


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_views_without_a_target_are_said_once_rather_than_scored(say: Say):
    written = say(f"use {LINES}", "run crlf")

    scores = written[written.index("\nscores\n") :]
    assert "note-" not in scores.split("no target")[0]
    assert "no target: judged note-comment, note-answer, note-graded" in scores

    written = say("run tag bytes")

    assert "note-" not in written.split("no target in any case")[0].split("trial:")[-1]
    assert "no target in any case: judged note-comment, note-answer, note-graded" in (
        written
    )


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_run_takes_a_case_that_sends_appendices_by_its_title(bench: Bench, say: Say):
    written = say(f"use {LINES}", "run whitespace with labs 8")

    assert f"trial: {LINES} × {QWEN_ARTIFACT} × whitespace with labs (seed 8)" in (
        written
    )
    [run] = ran(bench)
    _, case = bench.case_titled("whitespace with labs")
    assert [item.key.case for item in run.items] == [case]
    assert "no appendix xray of whitespace" in say("run whitespace with xray")


@pytest.mark.usefixtures("fake")
@pytest.mark.slow
def test_scores_say_an_offset_with_its_unit_and_their_details_as_text(say: Say):
    written = say(f"use {LINES}", "run matched")

    assert ["whole", "text", "@0", "Fake", "diagnosis", "B"] in cells(written)
    assert ["differential", "1", "1.", "Fake", "diagnosis", "B"] in cells(written)

    written = say("run noted")

    assert ["note-graded", "0.5", "by", "seed:", "0,", "0.5,", "1"] in cells(written)
    assert ["differential", "0", "not", "listed"] in cells(written)

import httpx2
import pytest

from chatddx.conftest import Recommit, Say, SayAs
from chatddx.history.models import RunModel
from chatddx.repl.commands import complete
from chatddx.repl.shell import Repl

pytestmark = pytest.mark.django_db


def lines(written: str) -> list[list[str]]:
    return [line.split() for line in written.splitlines()]


def test_a_run_ends_with_its_scores(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "run case-1")

    scores = written.index("scores\n")
    assert scores < written.index("recorded as run 1")
    assert lines(written[scores:])[1:3] == [
        ["first_mention", "17", "Fake", "diagnosis", "B"],
        ["reciprocal_rank", "0.5", "2.", "Fake", "diagnosis", "B"],
    ]


def test_a_plan_ends_with_its_warning_and_disposition_held_to_theirs(say: Say):
    written = say("cell plan qwen3-8b-awq@fake", "run case-1")

    assert lines(written[written.index("scores\n") :])[1:4] == [
        ["disposition_mentions", "0", "not", "named"],
        ["reciprocal_rank", "0.5", "2.", "fake", "diagnosis", "2"],
        ["warning_mentions", "1", "fake", "acute", "warning"],
    ]


def test_score_holds_the_outstanding_runs_and_sums_them_up(
    say: Say, recommit: Recommit
):
    _ = say(
        "cell free-text qwen3-8b-awq@fake",
        "run case-1",
        "cell plan qwen3-8b-awq@fake",
        "run case-1",
    )
    assert "nothing to score" in say("score")

    recommit(
        "case",
        "case-1",
        targets={"diagnosis": {"pattern": "fake & diagnosis & (a | 1)"}},
    )
    written = say("score")

    assert written.count("run ") == 2
    assert "free-text × qwen3-8b-awq@fake × case-1" in written
    assert ["reciprocal_rank", "1", "1.", "Fake", "diagnosis", "A"] in lines(written)
    assert ["first_mention", "0", "Fake", "diagnosis", "A"] in lines(written)
    assert ["scorer", "runs", "mean", "stderr", "without", "a", "value"] in lines(
        written
    )
    assert ["reciprocal_rank", "2", "1", "0"] in lines(written)
    assert ["first_mention", "1", "0", "0"] in lines(written)

    assert "nothing to score" in say("score")


def test_score_run_says_what_came_of_one_run(say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "run case-1")
    run = RunModel.objects.get()

    written = say(f"score {str(run.uuid)[:8]}")

    assert "scored already, as the scorers are now" in written
    assert ["reciprocal_rank", "0.5", "2.", "Fake", "diagnosis", "B"] in lines(written)

    _ = say("cell challenge-coercion-native qwen3-8b-awq@fake", "run case-1")
    latest = RunModel.objects.order_by("pk").last()
    assert latest is not None
    assert "no scorer applies to it" in say(f"score {str(latest.uuid)[:8]}")
    assert "alex has no run 'zzzz'" in say("score zzzz")


def test_score_says_an_errored_run_has_nothing_to_score(
    say_as: SayAs,
):
    def failing(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json={"error": {"message": "no such model"}})

    say = say_as(transport=httpx2.MockTransport(failing))
    written = say("cell free-text qwen3-8b-awq@fake", "run case-1")

    assert "scores" not in written
    assert "errored: nothing to score" in say(
        "score " + str(RunModel.objects.get().uuid)[:8]
    )


def test_scorers_lists_what_each_reads_and_what_the_cell_offers(say: Say):
    written = say("cell free-text qwen3-8b-awq@fake", "scorers")

    assert lines(written)[2:6] == [
        [
            "disposition_mentions",
            "mentions",
            "disposition",
            "disposition",
            "mean",
            "stderr",
            "archive",
            "—",
        ],
        [
            "first_mention",
            "first_mention",
            "text",
            "diagnosis",
            "mean",
            "stderr",
            "archive",
            "offers",
            "it",
        ],
        [
            "reciprocal_rank",
            "reciprocal_rank",
            "differential",
            "diagnosis",
            "mean",
            "stderr",
            "archive",
            "offers",
            "it",
        ],
        [
            "warning_mentions",
            "mentions",
            "warning",
            "warning",
            "mean",
            "stderr",
            "archive",
            "—",
        ],
    ]


def test_score_completes_the_outstanding_runs(repl: Repl, say: Say, recommit: Recommit):
    _ = say("cell free-text qwen3-8b-awq@fake", "run case-1")
    run = str(RunModel.objects.get().uuid)[:8]
    assert repl.completions()["score:run"] == []

    recommit(
        "case",
        "case-1",
        targets={"diagnosis": {"pattern": "fake & diagnosis & (a | 1)"}},
    )
    names = repl.completions()

    assert names["score:run"] == [run]
    assert names["replay:run"] == [run]
    assert complete(names, "score ") == [run]
    assert complete(names, "replay ") == [run]

    _ = say("score")

    assert repl.completions()["score:run"] == []

"""The identity's runs, and each again as it streamed."""

from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from chatddx.history.models import RunModel

type Say = Callable[..., str]

pytestmark = pytest.mark.django_db


def test_runs_lists_the_latest_first(say: Say):
    _ = say(
        "cell free-text qwen3-8b-awq@fake",
        "run case-1",
        "cell plan qwen3-8b-awq@fake",
        "run case-2",
    )

    rows = [line for line in say("runs").splitlines() if "×" in line]

    assert len(rows) == 2
    assert "plan × qwen3-8b-awq@fake × case-2" in rows[0]
    assert rows[0].split()[-3:] == ["valid", "reciprocal_rank", "0"]
    assert "free-text × qwen3-8b-awq@fake × case-1" in rows[1]
    assert rows[1].split()[-5:] == [
        "completed",
        "first_mention",
        "17",
        "reciprocal_rank",
        "0.5",
    ]

    [latest] = [line for line in say("runs 1").splitlines() if "×" in line]
    assert "plan" in latest


def test_runs_says_when_there_are_none(say: Say):
    assert "alex has no runs" in say("runs")
    assert "a count is a whole number, not 'x'" in say("runs x")


def test_replay_shows_a_run_again_as_it_streamed(say: Say):
    live = say("cell test-tools qwen3-8b-awq@fake", "run case-1").splitlines()
    replayed = say("replay").splitlines()

    start = next(i for i, line in enumerate(live) if line.startswith("trial:"))
    end = next(i for i, line in enumerate(live) if line.startswith("recorded as"))

    assert replayed[0].startswith("run ")
    assert replayed[0].endswith(": test-tools × qwen3-8b-awq@fake × case-1")
    assert ", completed, from a dev shell at " in replayed[1]
    assert replayed[2:] == live[start + 1 : end]
    assert "[result] asdf" in replayed


def test_replay_reads_a_structured_answer_again(say: Say):
    _ = say("cell plan qwen3-8b-awq@fake", "run case-1")

    replayed = say("replay")

    assert "valid" in replayed
    assert "differential\n  1. fake diagnosis 1" in replayed


def test_replay_takes_a_run_by_the_start_of_its_id(say: Say):
    _ = say("cell free-text qwen3-8b-awq@fake", "run case-1", "run case-2")
    first = RunModel.objects.order_by("pk").first()
    assert first is not None

    assert ": free-text × qwen3-8b-awq@fake × case-1" in say(
        f"replay {str(first.uuid)[:8]}"
    )
    assert "alex has no run 'zzzz'" in say("replay zzzz")
    assert "more than one run starts with ''" in say("replay ''")


def test_replay_of_a_run_whose_server_failed_says_why(
    say_through: Callable[[Any], Say],
):
    def handler(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json={"error": {"message": "no such model"}})

    say = say_through(httpx2.MockTransport(handler))
    _ = say("cell free-text qwen3-8b-awq@fake", "run case-1")

    replayed = say("replay")

    assert ", errored" in replayed
    assert "no such model" in replayed
    assert " in, " not in replayed

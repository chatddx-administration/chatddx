# pyright: basic
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from django.test import Client

from chatddx.conftest import Recommit
from chatddx.django.api.tests.conftest import Events

pytestmark = pytest.mark.django_db

type Run = Callable[..., Events]

FREE_TEXT = {"configuration": "free-text", "stack": "qwen3-8b-awq@fake"}


def score(client: Client, run: str | None = None) -> Any:
    return client.post(
        "/api/scores",
        {} if run is None else {"run": run},
        content_type="application/json",
    )


def values(scores: list[dict[str, Any]]) -> list[tuple[str, float | None]]:
    return [(row["scorer"], row["value"]) for row in scores]


def test_score_holds_the_outstanding_runs_and_sums_them_up(
    alex: Client, run: Run, recommit: Recommit
):
    _ = run(**FREE_TEXT, case="case-1", seed="none")
    _ = run(configuration="plan", stack="qwen3-8b-awq@fake", case="case-1", seed=2)

    assert score(alex).json() == {"runs": [], "summary": []}

    recommit(
        "case",
        "case-1",
        targets={"diagnosis": {"pattern": "fake & diagnosis & (a | 1)"}},
    )
    scored = score(alex).json()

    assert [row["run"]["description"] for row in scored["runs"]] == [
        "free-text × qwen3-8b-awq@fake × case-1",
        "plan × qwen3-8b-awq@fake × case-1 (seed 2)",
    ]
    assert values(scored["runs"][0]["made"]) == [
        ("first_mention", 0.0),
        ("reciprocal_rank", 1.0),
    ]
    assert values(scored["runs"][1]["made"]) == [("reciprocal_rank", 1.0)]
    assert {row["scorer"]: row for row in scored["summary"]}["reciprocal_rank"] == {
        "scorer": "reciprocal_rank",
        "scores": 2,
        "metrics": {"mean": 1.0, "stderr": 0.0},
        "without_value": 0,
    }
    assert score(alex).json()["runs"] == []


def test_score_run_says_what_came_of_one_run(
    alex: Client, run: Run, through: Callable[[Any], None]
):
    first = run(**FREE_TEXT, case="case-1")[0]["run"]
    already = score(alex, first[:8]).json()

    assert [row["unscored"] for row in already["runs"]] == ["scored already"]
    assert values(already["runs"][0]["run"]["scores"]) == [
        ("first_mention", 17.0),
        ("reciprocal_rank", 0.5),
    ]

    offered = run(
        configuration="challenge-coercion-native",
        stack="qwen3-8b-awq@fake",
        case="case-1",
    )[0]["run"]

    assert score(alex, offered).json()["runs"][0]["unscored"] == "no scorer applies"
    assert score(alex, "zzzz").status_code == 404
    assert score(alex, "").status_code == 409

    def failing(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json={"error": {"message": "no such model"}})

    through(httpx2.MockTransport(failing))
    errored = run(**FREE_TEXT, case="case-1")[0]["run"]

    assert score(alex, errored).json()["runs"][0]["unscored"] == "errored"


def test_a_trial_shows_your_runs_of_it_to_you_alone(
    alex: Client, run: Run, django_user_model: Any
):
    first = run(**FREE_TEXT, case="case-1", seed=3)[-1]["run"]
    _ = run(**FREE_TEXT, case="case-1", seed=3)

    trial = alex.get(f"/api/trials/{first['trial'][:8]}").json()

    assert trial["id"] == first["trial"]
    assert (trial["case"]["vignette"], trial["seed"]) == ("case vignette 1", 3)
    assert trial["stack"]["llm"]["fingerprint"].startswith("cddx-trail/")
    assert set(trial["configuration"]["output"]["views"]) == {"text", "differential"}
    assert [row["id"] for row in trial["runs"]][-1] == first["id"]
    assert len(trial["runs"]) == 2

    stranger = Client()
    stranger.force_login(django_user_model.objects.create_user(username="sam"))
    missing = stranger.get(f"/api/trials/{first['trial']}")

    assert missing.status_code == 404
    assert missing.json() == {
        "detail": f"sam has no runs of a trial '{first['trial']}'"
    }
    assert stranger.get("/api/runs").json() == []

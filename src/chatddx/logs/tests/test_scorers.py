import math
from collections.abc import Callable

import httpx2
import pytest
from inspect_ai.log import EvalLog

from chatddx.history.models import RunModel, TrialModel
from chatddx.logs.export import cell_log
from chatddx.logs.scorers import scored
from chatddx.logs.tests.conftest import Run
from chatddx.scoring.metrics import METRICS
from chatddx.scoring.score import Scoring

pytestmark = pytest.mark.django_db


def failing(_request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(502, json={"error": {"message": "the server went away"}})


def logs(identity: str = "alex") -> list[EvalLog]:
    cells = {
        (trial.configuration, trial.stack)
        for trial in TrialModel.objects.filter(runs__owner__name=identity)
    }

    return [
        scored(cell_log(identity, configuration, stack, "cell"), identity)
        for configuration, stack in cells
    ]


@pytest.mark.slow
def test_inspect_scores_each_sample_as_chatddx_scored_its_run(
    run_as: Callable[..., Run],
):
    run = run_as("alex")

    for configuration in ("plan", "free-text", "diagnoses", "test-tools"):
        run(
            f"cell {configuration} qwen3-8b-awq@fake",
            "run case-1",
            "run case-2",
            "run case-1 5",
        )

    run_as("alex", httpx2.MockTransport(failing))(
        "cell plan qwen3-8b-awq@fake", "run case-2 9"
    )

    scoring = Scoring("alex")
    held: set[str] = set()

    for log in logs():
        for sample in log.samples or []:
            recorded = RunModel.objects.get(uuid=sample.metadata["run"])
            by_chatddx = {
                score.scorer_name: score for score in scoring.latest(recorded)
            }
            by_inspect = sample.scores or {}

            assert set(by_chatddx) <= set(by_inspect)

            for name, score in by_inspect.items():
                made = by_chatddx.get(name)
                assert isinstance(score.value, float)

                if made is None:
                    assert math.isnan(score.value), (name, sample.id)
                    continue

                if made.value is None:
                    assert math.isnan(score.value)
                else:
                    assert score.value == made.value

                assert (score.answer, score.reason) == (made.answer, made.reason)
                assert score.metadata == {"target": made.target, "blob": made.blob}
                held.add(name)

    assert held == {
        "reciprocal_rank",
        "first_mention",
        "warning_mentions",
        "disposition_mentions",
    }


def test_an_errored_run_and_a_case_without_the_target_are_left_unscored(run: Run):
    run("cell plan qwen3-8b-awq@fake", "run case-2")

    [log] = logs()
    [sample] = log.samples or []
    scores = sample.scores or {}

    assert scores["warning_mentions"].reason == "the case has no warning target"
    assert isinstance(scores["warning_mentions"].value, float)
    assert math.isnan(scores["warning_mentions"].value)
    assert scores["reciprocal_rank"].value == 0.0


def test_a_scorers_metrics_are_chatddxs_sums_of_its_values(run: Run):
    run(
        "cell plan qwen3-8b-awq@fake",
        "run case-1",
        "run case-2",
    )

    [log] = logs()
    assert log.results is not None
    metrics = {
        score.name: {name: metric.value for name, metric in score.metrics.items()}
        for score in log.results.scores
    }
    values = [
        score.value
        for recorded in RunModel.objects.all()
        for score in Scoring("alex").latest(recorded)
        if score.scorer_name == "reciprocal_rank" and score.value is not None
    ]

    assert metrics["reciprocal_rank"] == {
        "mean": METRICS["mean"](values),
        "stderr": METRICS["stderr"](values),
    }
    assert log.eval.scorers is not None
    assert {scorer.name: scorer.options for scorer in log.eval.scorers}[
        "reciprocal_rank"
    ] == {
        "function": "chatddx.scoring.scorers.patterns:reciprocal_rank",
        "view": "differential",
        "target_kind": "diagnosis",
        "args": {},
    }

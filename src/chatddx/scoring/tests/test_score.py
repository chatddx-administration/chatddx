"""
Runs held to the scorers that apply to them: by the views their output
offers and the targets their case has, each score kept with the file and
target it was made with.
"""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from django.utils import timezone
from pydantic_ai import AgentRunResultEvent, UnexpectedModelBehavior

from chatddx.core import settings
from chatddx.dx.fake_vllm import FakeTransport, stream
from chatddx.history.models import RunModel, RunStatus, ScoreModel
from chatddx.history.record import Branches, Outcome, record
from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchSpec,
    ConfigurationTrailSchema,
)
from chatddx.repo.entities.model.pydantic import ModelBranchSpec
from chatddx.repo.entities.stack.pydantic import StackBranchSpec
from chatddx.repo.shufflers.branch import get_visible_branch_model
from chatddx.runtime.implementation import blob_of
from chatddx.runtime.resolution import resolve
from chatddx.runtime.trial import Trial
from chatddx.scoring import scorers
from chatddx.scoring.score import Scoring, latest

pytestmark = pytest.mark.django_db

STACK = "qwen3-8b-awq@fake"

SLICES = ("instruction", "output", "coercion", "reasoning", "sampling", "toolset")


@pytest.fixture(autouse=True)
def provisioned(provision: Callable[..., None]) -> None:
    provision()


async def outcome_of(trial: Trial) -> Outcome:
    """What came of `trial`, as the repl has it."""
    try:
        async with trial.stream() as events:
            async for event in events:
                if isinstance(event, AgentRunResultEvent):
                    return Outcome(RunStatus.COMPLETED, output=event.result.output)
    except UnexpectedModelBehavior as e:
        return Outcome(RunStatus.COMPLETED, valid=False, error=str(e))
    except Exception as e:  # noqa: BLE001
        return Outcome(RunStatus.ERRORED, error=str(e))

    return Outcome(RunStatus.COMPLETED, error="no answer came")


def ran(
    configuration: str,
    case: str = "case-1",
    transport: httpx2.AsyncBaseTransport | None = None,
) -> RunModel:
    """A run of `configuration` on `case`, against the fake vLLM, written down."""
    own = ConfigurationBranchSpec.model_validate(
        get_visible_branch_model("configuration", "alex", configuration)
    )
    slices: dict[str, Any] = {entity: getattr(own.target, entity) for entity in SLICES}
    cell = ConfigurationTrailSchema.model_validate(slices, from_attributes=True)
    stack = StackBranchSpec.model_validate(
        get_visible_branch_model("stack", "alex", STACK)
    )
    model = get_visible_branch_model("model", "alex", trail=stack.target.model.id)
    facts = ModelBranchSpec.model_validate(model).details.facts
    case_model = get_visible_branch_model("case", "alex", case)

    trial = Trial(
        resolve(cell, stack.details, facts, stack.target.serving),
        case_model.target.payload,
        transport=transport or FakeTransport(),
    )
    started = timezone.now()
    outcome = asyncio.run(outcome_of(trial))

    return record(
        "alex",
        cell,
        Branches(stack.id, model.pk),
        case_model.target_id,
        trial,
        outcome,
        started,
        timezone.now(),
    )


def made(run: RunModel) -> dict[str, tuple[float | None, str | None, str | None]]:
    return {s.scorer: (s.value, s.answer, s.reason) for s in Scoring().score(run)}


def test_free_text_is_held_to_its_rank_and_its_first_mention():
    assert made(ran("free-text")) == {
        "reciprocal_rank": (0.5, "2. Fake diagnosis B", None),
        "first_mention": (17.0, "Fake diagnosis B", None),
    }


def test_a_plan_is_held_to_its_rank_its_warning_and_its_disposition():
    assert made(ran("plan")) == {
        "reciprocal_rank": (0.5, "2. fake diagnosis 2", None),
        "warning_mentions": (1.0, "fake acute warning", None),
        "disposition_mentions": (0.0, None, "not named"),
    }


def test_a_scorer_applies_where_the_view_is_offered_and_the_target_expected():
    diagnoses = ran("diagnoses")
    raw = ran("baseline")
    without_warnings = ran("plan", "case-2")

    assert [s.name for s, _ in Scoring().applicable(diagnoses)] == ["reciprocal_rank"]
    assert [s.name for s, _ in Scoring().applicable(raw)] == ["first_mention"]
    assert [s.name for s, _ in Scoring().applicable(without_warnings)] == [
        "reciprocal_rank"
    ]


def test_a_score_keeps_the_file_and_the_target_it_was_made_with():
    [rank, _] = Scoring().score(ran("free-text"))

    patterns = Path(scorers.__file__).parent / "patterns.py"
    assert rank.blob == blob_of(patterns.read_bytes())
    assert (rank.view, rank.target) == ("differential", "fake & diagnosis & (b | 2)")


def test_a_run_scored_is_outstanding_again_when_its_target_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    run = ran("free-text")
    first = Scoring().score(run)

    assert Scoring().outstanding(run) == []
    assert Scoring().score(run) == []

    targets = tmp_path / "targets.toml"
    _ = targets.write_text('[case-1]\ndiagnosis = "fake & diagnosis & a"\n')
    monkeypatch.setattr(settings, "TARGETS_PATH", targets)

    assert [s.name for s, _ in Scoring().outstanding(run)] == [
        "reciprocal_rank",
        "first_mention",
    ]

    again = Scoring().score(run)

    assert [s.value for s in again] == [1.0, 0.0]
    assert ScoreModel.objects.filter(run=run).count() == len(first) + len(again)
    assert latest(run) == again


def test_an_errored_run_is_never_scored():
    def failing(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json={"error": {"message": "no such model"}})

    run = ran("free-text", transport=httpx2.MockTransport(failing))

    assert run.status == RunStatus.ERRORED
    assert Scoring().applicable(run) == []
    assert run not in Scoring().outstanding_runs("alex")


def test_a_run_that_came_to_no_answer_is_scored_as_such():
    def prose(_request: httpx2.Request) -> httpx2.Response:
        body: dict[str, Any] = {"model": "Qwen/Qwen3-8B-AWQ", "messages": []}
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(stream(body)).encode(),
        )

    run = ran("plan-prompted", transport=httpx2.MockTransport(prose))
    assert (run.status, run.output) == (RunStatus.COMPLETED, None)

    assert made(run) == {
        "reciprocal_rank": (0.0, None, "no answer"),
        "warning_mentions": (0.0, None, "no answer"),
        "disposition_mentions": (0.0, None, "no answer"),
    }


def test_outstanding_runs_are_those_with_a_scorer_to_go():
    scored = ran("free-text")
    unscored = ran("plan")
    _ = Scoring().score(scored)

    assert Scoring().outstanding_runs("alex") == [unscored]

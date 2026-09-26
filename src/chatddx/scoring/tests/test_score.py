import asyncio
from pathlib import Path
from typing import Any

import httpx2
import pytest
from django.utils import timezone
from pydantic_ai import AgentRunResultEvent, UnexpectedModelBehavior

from chatddx.conftest import Recommit
from chatddx.core.utils import ensure_identity
from chatddx.dev.fake_vllm import FakeTransport, stream
from chatddx.history.models import RunModel, RunStatus, ScoreModel
from chatddx.history.record import Branches, Outcome, record
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchOut,
    ConfigurationTrailIn,
)
from chatddx.repo.entities.llm.pydantic import LLMBranchOut
from chatddx.repo.entities.scorer.pydantic import (
    ScorerBranchDetails,
    ScorerTrailIn,
)
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.store.branch import commit, get_visible_branch_model
from chatddx.runtime.implementation import blob_of
from chatddx.runtime.resolution import resolve
from chatddx.runtime.run import Run
from chatddx.scoring import scorers
from chatddx.scoring.score import Scoring

pytestmark = pytest.mark.django_db

STACK = "qwen3-8b-awq@fake"

SLICES = ("instruction", "output", "coercion", "reasoning", "sampling", "toolset")


async def outcome_of(run: Run) -> Outcome:
    """What came of `run`, as the repl has it."""
    try:
        async with run.stream() as events:
            async for event in events:
                if isinstance(event, AgentRunResultEvent):
                    return Outcome(RunStatus.COMPLETED, answer=event.result.output)
    except UnexpectedModelBehavior as e:
        return Outcome(RunStatus.COMPLETED, valid=False, error=str(e))
    except Exception as e:  # noqa: BLE001
        return Outcome(RunStatus.ERRORED, error=str(e))

    return Outcome(RunStatus.COMPLETED, error="no answer came")


def ran(
    configuration: str,
    case: str = "case-1",
    transport: httpx2.AsyncBaseTransport | None = None,
    user: str = "alex",
) -> RunModel:
    """A run of `configuration` on `case`, against the fake vLLM, written down."""
    own = ConfigurationBranchOut.model_validate(
        get_visible_branch_model("configuration", "alex", configuration)
    )
    slices: dict[str, Any] = {entity: getattr(own.trail, entity) for entity in SLICES}
    cell = ConfigurationTrailIn.model_validate(slices, from_attributes=True)
    stack = StackBranchOut.model_validate(
        get_visible_branch_model("stack", "alex", STACK)
    )
    llm = get_visible_branch_model("llm", "alex", trail=stack.trail.llm.id)
    facts = LLMBranchOut.model_validate(llm).details.facts
    case_model = get_visible_branch_model("case", "alex", case)

    run = Run(
        resolve(cell, stack.details, facts, stack.trail.serving),
        case_model.trail.vignette,
        transport=transport or FakeTransport(),
    )
    started = timezone.now()
    outcome = asyncio.run(outcome_of(run))

    return record(
        user,
        cell,
        Branches(stack.id, llm.pk),
        case_model.trail_id,
        run,
        outcome,
        started,
        timezone.now(),
    )


def made(
    run: RunModel, user: str = "alex"
) -> dict[str, tuple[float | None, str | None, str | None]]:
    return {
        s.scorer_name: (s.value, s.answer, s.reason) for s in Scoring(user).score(run)
    }


def applicable(run: RunModel, user: str = "alex") -> list[str]:
    return [scorer.name for scorer, _, _ in Scoring(user).applicable(run)]


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

    assert applicable(diagnoses) == ["reciprocal_rank"]
    assert applicable(raw) == ["first_mention"]
    assert applicable(without_warnings) == ["reciprocal_rank"]


def test_the_scorers_are_the_archive_s_and_one_s_own():
    scorers = Scoring("alex").scorers

    assert [(s.name, s.owner) for s in scorers] == [
        ("disposition_mentions", "archive"),
        ("first_mention", "archive"),
        ("reciprocal_rank", "archive"),
        ("warning_mentions", "archive"),
    ]
    assert [(s.view, s.target_kind, s.metrics) for s in scorers[2:3]] == [
        ("differential", "diagnosis", ["mean", "stderr"])
    ]
    assert Scoring("nobody").scorers == ()


def test_a_scorer_of_one_s_own_shadows_the_archive_s_of_its_name():
    _ = commit(
        ScorerTrailIn(
            function="chatddx.scoring.scorers.patterns:mentions",
            view="text",
            target_kind="diagnosis",
        ),
        ScorerBranchDetails(name="reciprocal_rank", owner="alex", metrics=["mean"]),
    )

    assert made(ran("free-text")) == {
        "reciprocal_rank": (
            1.0,
            "Fake diagnosis A\nFake diagnosis B\nFake diagnosis C",
            None,
        ),
        "first_mention": (17.0, "Fake diagnosis B", None),
    }


def test_a_score_keeps_what_it_was_made_with_and_who_made_it():
    [_, rank] = Scoring("alex").score(ran("free-text"))

    patterns = Path(scorers.__file__).parent / "patterns.py"
    assert rank.blob == blob_of(patterns.read_bytes())
    assert (rank.scorer_name, rank.scorer.view, rank.scorer.target_kind) == (
        "reciprocal_rank",
        "differential",
        "diagnosis",
    )
    assert rank.target == "fake & diagnosis & (b | 2)"
    assert rank.case_branch is not None
    assert (rank.case_branch.owner.name, rank.case_branch.name) == (
        "archive",
        "case-1",
    )
    assert rank.owner.name == "alex"


def test_a_target_without_a_pattern_is_missing_for_the_pattern_scorers(
    recommit: Recommit,
):
    run = ran("free-text")
    recommit("case", "case-1", targets={"diagnosis": {"text": "Fake diagnosis B"}})

    assert applicable(run) == []


def test_a_run_scored_is_outstanding_again_when_its_target_changes(
    recommit: Recommit,
):
    run = ran("free-text")
    first = Scoring("alex").score(run)

    assert Scoring("alex").outstanding(run) == []
    assert Scoring("alex").score(run) == []

    recommit(
        "case", "case-1", targets={"diagnosis": {"pattern": "fake & diagnosis & a"}}
    )

    assert [s.name for s, _, _ in Scoring("alex").outstanding(run)] == [
        "first_mention",
        "reciprocal_rank",
    ]

    again = Scoring("alex").score(run)

    assert [s.value for s in again] == [0.0, 1.0]
    assert {s.case_branch_id for s in again} == {
        CaseBranchModel.objects.filter(owner__name="archive", name="case-1")
        .latest("pk")
        .pk
    }
    assert ScoreModel.objects.filter(run=run).count() == len(first) + len(again)
    assert Scoring("alex").latest(run) == again


def test_one_s_own_case_s_targets_shadow_the_archive_s(recommit: Recommit):
    run = ran("free-text")
    recommit(
        "case",
        "case-1",
        name="my-case",
        owner="alex",
        targets={"diagnosis": {"pattern": "fake & diagnosis & a"}},
    )

    assert made(run) == {
        "reciprocal_rank": (1.0, "1. Fake diagnosis A", None),
        "first_mention": (0.0, "Fake diagnosis A", None),
    }


def test_a_plan_that_rightly_raises_no_warning_is_held_to_none(recommit: Recommit):
    recommit(
        "case",
        "case-1",
        targets={
            "diagnosis": {"pattern": "fake & diagnosis & (b | 2)"},
            "warning": False,
            "disposition": {"pattern": "admit*"},
        },
    )

    assert made(ran("plan"))["warning_mentions"] == (
        0.0,
        "fake acute warning",
        "none expected",
    )
    assert ScoreModel.objects.get(scorer_name="warning_mentions").target is None


def test_each_identity_holds_a_run_to_its_own_scores():
    _ = CaseBranchModel.objects.get(
        owner__name="archive", name="case-1"
    ).collaborators.add(ensure_identity("bob"))
    run = ran("free-text")
    _ = Scoring("alex").score(run)

    assert [s.name for s, _, _ in Scoring("bob").outstanding(run)] == []
    assert Scoring("bob").latest(run) == []
    assert Scoring("alex").outstanding(run) == []


def test_an_errored_run_is_never_scored():
    def failing(_request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(400, json={"error": {"message": "no such model"}})

    run = ran("free-text", transport=httpx2.MockTransport(failing))

    assert run.status == RunStatus.ERRORED
    assert Scoring("alex").applicable(run) == []
    assert run not in Scoring("alex").outstanding_runs()


def test_a_run_that_came_to_no_answer_is_scored_as_such():
    def prose(_request: httpx2.Request) -> httpx2.Response:
        body: dict[str, Any] = {"model": "Qwen/Qwen3-8B-AWQ", "messages": []}
        return httpx2.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(stream(body)).encode(),
        )

    run = ran("plan-prompted", transport=httpx2.MockTransport(prose))
    assert (run.status, run.answer) == (RunStatus.COMPLETED, None)

    assert made(run) == {
        "reciprocal_rank": (0.0, None, "no answer"),
        "warning_mentions": (0.0, None, "no answer"),
        "disposition_mentions": (0.0, None, "no answer"),
    }


def test_outstanding_runs_are_those_with_a_scorer_to_go():
    scored = ran("free-text")
    unscored = ran("plan")
    _ = Scoring("alex").score(scored)

    assert Scoring("alex").outstanding_runs() == [unscored]

# pyright: basic
"""
Runs and what came of them: the repl's run, batch, runs, replay and score. A
run or a trial is named by its id, or the start of it.
"""

from typing import Any

from django.http import HttpRequest
from ninja import Query, Router
from ninja.errors import HttpError

from chatddx.bench.bench import Ambiguous, Bench, NotFound
from chatddx.django.api.cell import held
from chatddx.django.api.identity import identity_of
from chatddx.django.api.schemas import (
    BatchIn,
    Exchange,
    MessageOut,
    Page,
    RunIn,
    RunOut,
    RunScored,
    RunSummary,
    ScoreIn,
    ScoringOut,
    TrialOut,
)
from chatddx.django.api.sending import Batch, EventStream, Sending
from chatddx.django.api.showing import run_of, scores_of, summary_of, sums_of
from chatddx.history.models import MessageModel, RunModel, RunStatus, TrialModel
from chatddx.repo.entities.case.pydantic import CaseTrailOut
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailOut
from chatddx.repo.entities.stack.pydantic import StackTrailOut
from chatddx.repo.utils import resolve_trail
from chatddx.scoring.score import Scoring

# where runs go in place of each stack's endpoint: the fake vLLM, in tests
TRANSPORT: Any = None

router = Router(tags=["runs"])

EVENTS = {"text/event-stream": {"schema": {"$ref": "#/components/schemas/Event"}}}

STREAMED = {
    "responses": {
        200: {
            "description": "the run's events, and pydantic-ai's by their event_kind",
            "content": EVENTS,
        }
    }
}

BATCHED = {"responses": {200: {"description": "the runs' events", "content": EVENTS}}}


@router.post("/runs", response=RunOut, openapi_extra=STREAMED)
def run(request: HttpRequest, spec: RunIn):
    """Run the cell on a case or a vignette, stream it, record it and score it."""
    sending = Sending.of(*held(request, spec, TRANSPORT), spec)

    if spec.stream:
        return EventStream([sending])

    return sending.through().run


@router.post("/batch", openapi_extra=BATCHED)
def batch(request: HttpRequest, spec: BatchIn):
    """Run the cell on each case with any of the tags, then sum up the scores."""
    batched = Batch(*held(request, spec, TRANSPORT), spec)
    return EventStream(batched.sendings, [batched.batched], batched.summarized)


@router.get("/runs", response=list[RunSummary])
def runs(request: HttpRequest, page: Query[Page]):
    """The identity's runs, the latest first."""
    identity = identity_of(request)
    scoring = Scoring(identity)
    found = (
        RunModel.objects.filter(owner__name=identity)
        .select_related("trial", "conversation")
        .prefetch_related("scores")
        .order_by("-timestamp", "-pk")[page.offset : page.offset + page.limit]
    )

    return [summary_of(run, scoring) for run in found]


@router.get("/runs/{run}", response=RunOut)
def one(request: HttpRequest, run: str):
    """The run as it is recorded: replay it with its messages."""
    bench = Bench(identity_of(request))
    return run_of(bench.run_named(run), Scoring(bench.identity))


@router.get("/runs/{run}/messages", response=list[MessageOut])
def messages(request: HttpRequest, run: str):
    """The run's messages, as pydantic-ai keeps them."""
    found = Bench(identity_of(request)).run_named(run)

    return [
        MessageOut(
            run=message.run_uuid,
            role=message.role,
            kind=message.kind,
            payload=message.payload,
            timestamp=message.timestamp,
        )
        for message in MessageModel.objects.filter(
            conversation=found.conversation, run_uuid=found.uuid
        )
    ]


@router.get("/runs/{run}/exchange", response=Exchange)
def exchange(request: HttpRequest, run: str):
    """What the run sent and got back, byte for byte."""
    found = Bench(identity_of(request)).run_named(run)
    return Exchange(requests=found.requests, responses=found.responses)


@router.post("/scores", response=ScoringOut)
def score(request: HttpRequest, spec: ScoreIn):
    """Hold the outstanding runs, or the one named, to the scorers that apply."""
    bench = Bench(identity_of(request))
    scoring = Scoring(bench.identity)
    held_to = (
        scoring.outstanding_runs() if spec.run is None else [bench.run_named(spec.run)]
    )
    scored: list[RunScored] = []
    made_all = []

    for held_run in held_to:
        try:
            made = scoring.score(held_run)
        except ValueError as e:
            raise HttpError(422, str(e)) from None

        made_all += made
        scored.append(
            RunScored(
                run=summary_of(held_run, scoring),
                made=scores_of(made),
                unscored=(
                    None
                    if made
                    else "errored"
                    if held_run.status == RunStatus.ERRORED
                    else "no scorer applies"
                    if not scoring.applicable(held_run)
                    else "scored already"
                ),
            )
        )

    return ScoringOut(runs=scored, summary=sums_of(scoring.summed(made_all)))


@router.get("/trials/{trial}", response=TrialOut)
def trial(request: HttpRequest, trial: str):
    """A trial the identity ran, and its runs of it."""
    bench = Bench(identity_of(request))
    found = list(
        TrialModel.objects.filter(
            uuid__startswith=trial, runs__owner__name=bench.identity
        )
        .distinct()
        .select_related("configuration", "stack", "case")[:2]
    )

    if not found:
        raise NotFound(f"{bench.identity} has no runs of a trial '{trial}'")

    if len(found) > 1:
        raise Ambiguous(f"more than one trial starts with '{trial}'")

    [held_trial] = found
    scoring = Scoring(bench.identity)
    its_runs = (
        held_trial.runs.filter(owner__name=bench.identity)
        .select_related("trial", "conversation")
        .prefetch_related("scores")
        .order_by("-timestamp", "-pk")
    )

    return TrialOut(
        id=held_trial.uuid,
        timestamp=held_trial.timestamp,
        configuration=ConfigurationTrailOut.model_validate(
            resolve_trail(held_trial.configuration)
        ),
        stack=StackTrailOut.model_validate(resolve_trail(held_trial.stack)),
        case=CaseTrailOut.model_validate(held_trial.case),
        seed=held_trial.seed,
        runs=[summary_of(run, scoring) for run in its_runs],
    )

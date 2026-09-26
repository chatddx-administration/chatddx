# pyright: basic
"""The history the repo has no schemas of, and what came of the identity's runs."""

from typing import Any

from django.db.models import prefetch_related_objects
from pydantic import JsonValue

from chatddx.bench.bench import Bench
from chatddx.django.api.schemas import (
    BranchRow,
    ReadOut,
    RunOut,
    RunSummary,
    RunsWith,
    ScoreOut,
    ScorerSum,
    ToolRan,
)
from chatddx.history.models import RunModel, RunStatus, RunToolBranchModel, ScoreModel
from chatddx.repo.entities.case.pydantic import CaseTrailOut, pattern_of
from chatddx.repo.entities.client.pydantic import ClientTrailOut
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailOut
from chatddx.repo.entities.output.pydantic import VIEWS, OutputTrailBase
from chatddx.repo.entities.stack.pydantic import StackTrailOut
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.utils import resolve_trail
from chatddx.scoring.score import Scoring, Summed
from chatddx.scoring.scorers.patterns import unread_pattern


def detail_of(bench: Bench, entity: EntityName, model: BranchModel) -> dict[str, Any]:
    """A branch, as its entity's Detail has it, and the identity's runs with it."""
    runs = bench.runs_with(entity, model.trail_id)
    scoring = Scoring(bench.identity)
    made = [score for run in runs for score in scoring.latest(run)]

    if entity == "scorer":
        made = [score for score in made if score.scorer_id == model.trail_id]

    targets: dict[str, Any] = model.details.get("targets", {})
    unread = {
        kind: why
        for kind, target in targets.items()
        if (pattern := pattern_of(target)) and (why := unread_pattern(pattern))
    }

    return {
        "branch": model,
        "runs": RunsWith(
            runs=len(runs),
            errored=sum(run.status == RunStatus.ERRORED for run in runs),
            scorers=sums_of(scoring.summed(made)),
        ),
        "unread": unread,
    }


def score_of(score: ScoreModel) -> ScoreOut:
    return ScoreOut(
        scorer=score.scorer_name,
        scorer_fingerprint=score.scorer.fingerprint,
        value=score.value,
        answer=score.answer,
        reason=score.reason,
        target=score.target,
        blob=score.blob,
        timestamp=score.timestamp,
    )


def scores_of(scores: list[ScoreModel]) -> list[ScoreOut]:
    prefetch_related_objects(scores, "scorer")
    return [score_of(score) for score in scores]


def sums_of(summed: list[Summed]) -> list[ScorerSum]:
    return [
        ScorerSum(
            scorer=row.scorer.name,
            scores=row.scores,
            metrics=dict(row.metrics),
            without_value=row.without,
        )
        for row in summed
    ]


def summary_of(run: RunModel, scoring: Scoring) -> RunSummary:
    return RunSummary(
        id=run.uuid,
        trial=run.trial.uuid,
        timestamp=run.timestamp,
        description=run.conversation.description if run.conversation else None,
        status=run.status,
        valid=run.valid,
        error=run.error,
        scores=scores_of(scoring.latest(run)),
    )


def run_of(run: RunModel, scoring: Scoring) -> RunOut:
    trial = run.trial
    ran = RunToolBranchModel.objects.filter(run=run).select_related(
        "tool_branch__owner"
    )

    return RunOut(
        **summary_of(run, scoring).model_dump(),
        number=trial.runs.filter(pk__lte=run.pk).count(),
        started=run.started,
        finished=run.finished,
        finish_reason=run.finish_reason,
        answer=run.answer,
        views=(
            None if run.answer is None else views_of(scoring.output_of(run), run.answer)
        ),
        configuration=ConfigurationTrailOut.model_validate(
            resolve_trail(trial.configuration)
        ),
        stack=StackTrailOut.model_validate(resolve_trail(trial.stack)),
        case=CaseTrailOut.model_validate(trial.case),
        seed=trial.seed,
        client=None
        if run.client is None
        else ClientTrailOut.model_validate(run.client),
        client_rev=run.client_rev,
        read=ReadOut(
            stack=_row(run.stack_branch),
            llm=_row(run.llm_branch),
            tools=[
                ToolRan(
                    id=link.tool_branch.pk,
                    name=link.tool_branch.name,
                    owner=link.tool_branch.owner.name,
                    blob=link.blob,
                )
                for link in ran
            ],
        ),
    )


def views_of(output: OutputTrailBase, answer: JsonValue) -> dict[str, list[JsonValue]]:
    return {view: output.view(view, answer) for view in VIEWS if view in output.views}


def _row(branch: BranchModel | None) -> BranchRow | None:
    if branch is None:
        return None

    return BranchRow(id=branch.pk, name=branch.name, owner=branch.owner.name)

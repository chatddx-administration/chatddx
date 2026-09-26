# pyright: basic
"""The registry and its history as the API shows them to the identity."""

from typing import Any

from django.db.models import prefetch_related_objects
from pydantic import JsonValue

from chatddx.django.api.schemas import (
    Branch,
    BranchDetail,
    BranchRow,
    ClientOut,
    ReadOut,
    ReasoningOut,
    Ref,
    Refusal,
    RunOut,
    RunSummary,
    RunsWith,
    SamplingOut,
    ScoreOut,
    ScorerSum,
    TargetOut,
    ToolRan,
)
from chatddx.history.models import RunModel, RunStatus, RunToolBranchModel, ScoreModel
from chatddx.repl.bench import Bench, greedy, unread_pattern
from chatddx.repl.cell import SLICES
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.case.pydantic import TARGET_KINDS, CaseDetails, Expected
from chatddx.repo.entities.output.pydantic import VIEWS, OutputTrailBase
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.families.pydantic import TrailOut
from chatddx.runtime.resolution import Reasoning, Sampling, SliceRefusal
from chatddx.scoring.score import Scoring, Summed


def ref_of(
    bench: Bench, entity: EntityName, trail: Any, name: str | None = None
) -> Ref:
    return Ref(
        entity=entity,
        name=name or bench.name_of(entity, trail),
        fingerprint=trail.fingerprint,
    )


def maybe_ref_of(bench: Bench, entity: EntityName, trail: Any) -> Ref | None:
    return None if trail is None else ref_of(bench, entity, trail)


def branches_of(
    bench: Bench, entity: EntityName, models: list[BranchModel]
) -> list[Branch]:
    prefetch_related_objects(models, "tags", "collaborators")
    return [branch_of(bench, entity, model) for model in models]


def branch_of(bench: Bench, entity: EntityName, model: BranchModel) -> Branch:
    registered = entity_of(entity)
    trail = registered.trail_out.model_validate(model.trail)

    return Branch(
        entity=entity,
        id=model.pk,
        name=model.name,
        owner=model.owner.name,
        timestamp=model.timestamp,
        versions=model.version_count,
        fingerprint=trail.fingerprint,
        trail=content_of(bench, trail),
        details=_in_order(_details(entity, model).model_dump(mode="json")),
        tags=[tag.name for tag in model.tags.all()],
        collaborators=[identity.name for identity in model.collaborators.all()],
    )


def detail_of(bench: Bench, entity: EntityName, model: BranchModel) -> BranchDetail:
    """A branch, with what came of the identity's runs with its trail."""
    runs = bench.runs_with(entity, model.trail_id)
    scoring = Scoring(bench.identity)
    made = [score for run in runs for score in scoring.latest(run)]

    if entity == "scorer":
        made = [score for score in made if score.scorer_id == model.trail_id]

    return BranchDetail(
        **branches_of(bench, entity, [model])[0].model_dump(),
        runs=RunsWith(
            runs=len(runs),
            errored=sum(run.status == RunStatus.ERRORED for run in runs),
            scorers=sums_of(scoring.summed(made)),
        ),
        targets=(targets_of(_details(entity, model)) if entity == "case" else None),
    )


def targets_of(details: Any) -> list[TargetOut]:
    assert isinstance(details, CaseDetails)
    shown: list[TargetOut] = []

    for kind in TARGET_KINDS:
        target = details.targets.get(kind)
        expected = target if isinstance(target, Expected) else None
        pattern = expected.pattern if expected else None

        shown.append(
            TargetOut(
                kind=kind,
                none_expected=target is False,
                text=expected.text if expected else None,
                pattern=pattern,
                unread=None if pattern is None else unread_pattern(pattern),
            )
        )

    return shown


def content_of(bench: Bench, trail: TrailOut) -> dict[str, Any]:
    """A trail's fields but its id and timestamp, each relation a `Ref`."""
    own = set(TrailOut.model_fields)
    content = _in_order(trail.model_dump(mode="json", exclude=own))

    for field in content:
        value = getattr(trail, field)

        match value:
            case TrailOut():
                content[field] = _ref(bench, value).model_dump(mode="json")
            case [TrailOut(), *_]:
                content[field] = [
                    _ref(bench, item).model_dump(mode="json") for item in value
                ]
            case _:
                pass

    return content


def _details(entity: EntityName, model: BranchModel) -> Any:
    """The branch's details, each at its default where the version leaves it out."""
    details = entity_of(entity).branch_out.model_fields["details"].annotation
    assert details is not None

    return details.model_validate(model.details)


def _in_order(fields: dict[str, Any]) -> dict[str, Any]:
    """A mapping keyed by targets' kinds or views, in their order: jsonb keeps none."""
    for field, value in fields.items():
        if not isinstance(value, dict) or not value:
            continue

        for vocabulary in (TARGET_KINDS, VIEWS):
            if set(value) <= set(vocabulary):
                fields[field] = {key: value[key] for key in vocabulary if key in value}

    return fields


def _ref(bench: Bench, trail: TrailOut) -> Ref:
    return ref_of(bench, entity_of(trail).name, trail)


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


def run_of(bench: Bench, run: RunModel, scoring: Scoring) -> RunOut:
    trial = run.trial
    configuration = trial.configuration
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
        configuration=ref_of(bench, "configuration", configuration),
        slices=slices_of(bench, configuration),
        stack=ref_of(bench, "stack", trial.stack),
        case=ref_of(bench, "case", trial.case),
        seed=trial.seed,
        client=(
            None
            if run.client is None
            else ClientOut(
                build=run.client.build,
                rev=run.client_rev,
                packages=run.client_packages,
            )
        ),
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


def slices_of(bench: Bench, configuration: Any) -> dict[str, Ref | None]:
    return {
        entity: maybe_ref_of(bench, entity, getattr(configuration, entity))
        for entity in SLICES
    }


def views_of(output: OutputTrailBase, answer: JsonValue) -> dict[str, list[JsonValue]]:
    return {view: output.view(view, answer) for view in VIEWS if view in output.views}


def refusals_of(refusals: list[SliceRefusal]) -> list[Refusal]:
    return [
        Refusal(slice=refusal.slice, reason=refusal.reason, kind=refusal.kind)
        for refusal in refusals
    ]


def reasoning_of(reasoning: Reasoning | None) -> ReasoningOut | None:
    if reasoning is None:
        return None

    return ReasoningOut(
        effort=reasoning.effort, intent=reasoning.intent, writes=reasoning.writes
    )


def sampling_of(sampling: Sampling | None) -> SamplingOut | None:
    if sampling is None:
        return None

    return SamplingOut(
        source=sampling.source, writes=sampling.writes, greedy=greedy(sampling)
    )


def _row(branch: BranchModel | None) -> BranchRow | None:
    if branch is None:
        return None

    return BranchRow(id=branch.pk, name=branch.name, owner=branch.owner.name)

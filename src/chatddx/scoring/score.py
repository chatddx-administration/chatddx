from dataclasses import dataclass
from typing import Any, cast

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.history.models import RunModel, RunStatus, ScoreModel
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import TargetKind, pattern_of
from chatddx.repo.entities.output.pydantic import OutputTrailOut, View
from chatddx.repo.entities.scorer.django import ScorerTrailModel
from chatddx.repo.entities.scorer.pydantic import Metric, ScorerDetails
from chatddx.repo.store.branch import select_visible_branch_models
from chatddx.repo.store.trail import load_trail
from chatddx.runtime.implementation import (
    SCORER_PACKAGE,
    Implementation,
    implementation,
)
from chatddx.scoring.metrics import METRICS

ARCHIVE = settings.ARCHIVE_IDENTITY_NAME


@dataclass(frozen=True)
class VisibleScorer:
    name: str
    owner: str
    trail: ScorerTrailModel
    metrics: list[Metric]

    @property
    def view(self) -> View:
        return cast(View, self.trail.view)

    @property
    def target_kind(self) -> TargetKind | None:
        return cast(TargetKind | None, self.trail.target_kind)

    @property
    def args(self) -> dict[str, Any]:
        return self.trail.args


type Applicable = tuple[VisibleScorer, str | None, CaseBranchModel | None]


@dataclass(frozen=True)
class Summed:
    scorer: VisibleScorer
    scores: int
    metrics: dict[Metric, float | None]
    without: int


class Scoring:
    def __init__(self, identity: str):
        self.identity: str = identity
        self.owner_id: int | None = (
            IdentityModel.objects.filter(name=identity)
            .values_list("pk", flat=True)
            .first()
        )
        self.scorers: tuple[VisibleScorer, ...] = tuple(self._visible())
        self._implementations: dict[int, Implementation] = {}
        self._outputs: dict[int, OutputTrailOut] = {}
        self._cases: dict[int, CaseBranchModel | None] = {}

    def _visible(self) -> list[VisibleScorer]:
        scorers: list[VisibleScorer] = []

        for branch in select_visible_branch_models("scorer", self.identity, ARCHIVE):
            if any(scorer.trail.pk == branch.trail_id for scorer in scorers):
                continue

            scorers.append(
                VisibleScorer(
                    name=branch.name,
                    owner=branch.owner.name,
                    trail=cast(ScorerTrailModel, branch.trail),
                    metrics=ScorerDetails.model_validate(branch.details).metrics,
                )
            )

        return scorers

    def implementation_of(self, scorer: VisibleScorer) -> Implementation:
        if scorer.trail.pk not in self._implementations:
            try:
                ran = implementation(scorer.trail.function, SCORER_PACKAGE)
            except ValueError as e:
                raise ValueError(f"the scorer '{scorer.name}' can't run: {e}") from None

            self._implementations[scorer.trail.pk] = ran

        return self._implementations[scorer.trail.pk]

    def applicable(self, run: RunModel) -> list[Applicable]:
        if run.status != RunStatus.COMPLETED:
            return []

        views = self.output_of(run).views
        case = self.case_of(run)
        targets: dict[str, object] = case.details.get("targets", {}) if case else {}
        found: list[Applicable] = []

        for scorer in self.scorers:
            if scorer.view not in views:
                continue

            if scorer.target_kind is None:
                found.append((scorer, None, None))
            elif scorer.target_kind in targets:
                target = targets[scorer.target_kind]

                if target is False:
                    found.append((scorer, None, case))
                elif (pattern := pattern_of(target)) is not None:
                    found.append((scorer, pattern, case))

        return found

    def outstanding(self, run: RunModel) -> list[Applicable]:
        scored = {
            (score.scorer_id, score.target, score.blob)
            for score in run.scores.all()
            if score.owner_id == self.owner_id
        }

        return [
            (scorer, target, case)
            for scorer, target, case in self.applicable(run)
            if (scorer.trail.pk, target, self.implementation_of(scorer).blob)
            not in scored
        ]

    def outstanding_runs(self) -> list[RunModel]:
        runs = (
            RunModel.objects.filter(
                owner__name=self.identity, status=RunStatus.COMPLETED
            )
            .select_related("trial__configuration__output", "conversation")
            .prefetch_related("scores")
            .order_by("timestamp", "pk")
        )

        return [run for run in runs if self.outstanding(run)]

    def score(self, run: RunModel) -> list[ScoreModel]:
        output = self.output_of(run)
        made: list[ScoreModel] = []

        for scorer, target, case in self.outstanding(run):
            items = (
                None
                if run.answer is None
                else [str(item) for item in output.view(scorer.view, run.answer)]
            )
            ran = self.implementation_of(scorer)
            scored = ran.function(items, target, **scorer.args)
            made.append(
                ScoreModel.objects.create(
                    run=run,
                    owner_id=self.owner_id,
                    scorer=scorer.trail,
                    scorer_name=scorer.name,
                    case_branch=case,
                    target=target,
                    blob=ran.blob,
                    value=scored.value,
                    answer=scored.answer,
                    reason=scored.reason,
                )
            )

        return made

    def summed(self, made: list[ScoreModel]) -> list[Summed]:
        """Each scorer's scores among `made`, and its metrics of their values."""
        found: list[Summed] = []

        for scorer in self.scorers:
            values = [
                score.value for score in made if score.scorer_id == scorer.trail.pk
            ]

            if not values:
                continue

            counted = [value for value in values if value is not None]
            found.append(
                Summed(
                    scorer,
                    len(values),
                    {
                        metric: METRICS[metric](counted) if counted else None
                        for metric in scorer.metrics
                    },
                    len(values) - len(counted),
                )
            )

        return found

    def latest(self, run: RunModel) -> list[ScoreModel]:
        found = {
            score.scorer_name: score
            for score in run.scores.all()
            if score.owner_id == self.owner_id
        }
        order = [scorer.name for scorer in self.scorers]

        return sorted(
            found.values(),
            key=lambda score: (
                order.index(score.scorer_name)
                if score.scorer_name in order
                else len(order),
                score.scorer_name,
            ),
        )

    def output_of(self, run: RunModel) -> OutputTrailOut:
        output = run.trial.configuration.output

        if output.pk not in self._outputs:
            self._outputs[output.pk] = cast(
                OutputTrailOut,
                load_trail("output", output.fingerprint, OutputTrailOut),
            )

        return self._outputs[output.pk]

    def case_of(self, run: RunModel) -> CaseBranchModel | None:
        case_id = run.trial.case_id

        if case_id not in self._cases:
            rows = CaseBranchModel.objects.filter(trail_id=case_id).order_by(
                "-timestamp", "-pk"
            )
            self._cases[case_id] = (
                rows.filter(owner__name=self.identity).first()
                or rows.filter(
                    owner__name=ARCHIVE, collaborators__name=self.identity
                ).first()
            )

        return self._cases[case_id]

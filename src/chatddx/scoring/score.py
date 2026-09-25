# pyright: basic
"""
Holding runs to the scorers that apply to them, and writing down what each
made of them (datamodel.md §7).

A scorer is the registry's: a function in one of chatddx's own scorer files,
the view it reads, and the kind of target it holds that to. Whoever scores
holds runs to the scorers they can see, their own and the archive's, and to
the targets of the case branch that holds the run's case: their own, or else
the archive's. A scorer applies to a completed run whose output offers its
view, and whose case has its kind of target if it needs one. A run is
outstanding for a scorer, for whoever scores, until it has a score of theirs
from the scorer's trail with the target and the file's blob as they are now:
an edit to any of them makes it outstanding again. An errored run is never
scored.
"""

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

ARCHIVE = settings.ARCHIVE_IDENTITY_NAME


@dataclass(frozen=True)
class VisibleScorer:
    """A scorer as whoever scores sees it: its name, owner, content and metrics."""

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


# a scorer that applies to a run, the target it holds the run to, and the
# case branch that target was read from
type Applicable = tuple[VisibleScorer, str | None, CaseBranchModel | None]


class Scoring:
    """
    The scorers `identity` can see, as their files are now, and the targets
    it holds runs to: read once, for one run or many.
    """

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
        """Its own scorers and the archive's, a trail named once."""
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
        """What the scorer runs, as its file is now."""
        if scorer.trail.pk not in self._implementations:
            try:
                ran = implementation(scorer.trail.function, SCORER_PACKAGE)
            except ValueError as e:
                raise ValueError(f"the scorer '{scorer.name}' can't run: {e}") from None

            self._implementations[scorer.trail.pk] = ran

        return self._implementations[scorer.trail.pk]

    def applicable(self, run: RunModel) -> list[Applicable]:
        """Each scorer that applies to `run`, and the target it holds the run to."""
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
        """Each scorer `run` has no score of the identity's from, as it is now."""
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
        """The identity's runs outstanding for any scorer, oldest first."""
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
        """Hold `run` to each scorer it is outstanding for, and write each down."""
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

    def latest(self, run: RunModel) -> list[ScoreModel]:
        """
        The identity's latest score of `run` from each scorer, by its name: the
        scorers it can see first, in their order.
        """
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
        """
        The case branch whose targets `run` is held to: the newest row of the
        identity's own that holds the run's case, or else of the archive's that
        it can see.
        """
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

# pyright: basic
"""
Holding runs to the scorers that apply to them, and writing down what each
made of them.

A scorer is a function in one of chatddx's own scorer files, the view it
reads, and the target it holds that to. It applies to a completed run whose
output offers its view and whose case has its target in `targets.toml`, by
the case's name in the inventory. A run is outstanding for a scorer until it
has a score from the scorer's file and the target as they are now: an edit
to either makes it outstanding again. An errored run is never scored.
"""

import tomllib
from dataclasses import dataclass
from typing import cast

from chatddx.core import settings
from chatddx.history.models import RunModel, RunStatus, ScoreModel
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.output.pydantic import OutputTrailSpec, View
from chatddx.repo.shufflers.trail import load_trail
from chatddx.runtime.implementation import (
    SCORERS as PACKAGE,
    Implementation,
    implementation,
)

PATTERNS = f"{PACKAGE}.patterns"


@dataclass(frozen=True)
class Scorer:
    name: str
    entry_point: str
    view: View
    target: str


SCORERS: tuple[Scorer, ...] = (
    Scorer(
        "reciprocal_rank", f"{PATTERNS}:reciprocal_rank", "differential", "diagnosis"
    ),
    Scorer("first_mention", f"{PATTERNS}:first_mention", "text", "diagnosis"),
    Scorer("warning_mentions", f"{PATTERNS}:mentions", "warning", "warning"),
    Scorer(
        "disposition_mentions", f"{PATTERNS}:mentions", "disposition", "disposition"
    ),
)


class Scoring:
    """
    The scorers as their files are now, and the targets as `targets.toml`
    has them: read once, for one run or many.
    """

    def __init__(self):
        self.implementations: dict[str, Implementation] = {
            scorer.name: implementation(scorer.entry_point, PACKAGE)
            for scorer in SCORERS
        }
        self.targets: dict[str, dict[str, str]] = tomllib.loads(
            settings.TARGETS_PATH.read_text()
        )
        self._outputs: dict[int, OutputTrailSpec] = {}
        self._cases: dict[int, str | None] = {}

    def applicable(self, run: RunModel) -> list[tuple[Scorer, str]]:
        """Each scorer that applies to `run`, and the target it holds the run to."""
        if run.status != RunStatus.COMPLETED:
            return []

        views = self.output_of(run).views
        expected = self.targets.get(self.case_of(run) or "", {})

        return [
            (scorer, expected[scorer.target])
            for scorer in SCORERS
            if scorer.view in views and scorer.target in expected
        ]

    def outstanding(self, run: RunModel) -> list[tuple[Scorer, str]]:
        """Each scorer `run` has no score from, as its file and target are now."""
        scored = {(s.scorer, s.view, s.target, s.blob) for s in run.scores.all()}

        return [
            (scorer, target)
            for scorer, target in self.applicable(run)
            if (scorer.name, scorer.view, target, self.blob_of(scorer)) not in scored
        ]

    def outstanding_runs(self, identity: str) -> list[RunModel]:
        """The identity's runs outstanding for any scorer, oldest first."""
        runs = (
            RunModel.objects.filter(owner__name=identity, status=RunStatus.COMPLETED)
            .select_related("trial__configuration__output", "session")
            .prefetch_related("scores")
            .order_by("timestamp", "pk")
        )

        return [run for run in runs if self.outstanding(run)]

    def score(self, run: RunModel) -> list[ScoreModel]:
        """Hold `run` to each scorer it is outstanding for, and write each down."""
        output = self.output_of(run)
        made: list[ScoreModel] = []

        for scorer, target in self.outstanding(run):
            items = (
                None
                if run.output is None
                else [str(item) for item in output.view(scorer.view, run.output)]
            )
            ran = self.implementations[scorer.name]
            scored = ran.function(items, target)
            made.append(
                ScoreModel.objects.create(
                    run=run,
                    scorer=scorer.name,
                    view=scorer.view,
                    target=target,
                    blob=ran.blob,
                    value=scored.value,
                    answer=scored.answer,
                    reason=scored.reason,
                )
            )

        return made

    def blob_of(self, scorer: Scorer) -> str:
        return self.implementations[scorer.name].blob

    def output_of(self, run: RunModel) -> OutputTrailSpec:
        output = run.trial.configuration.output

        if output.pk not in self._outputs:
            self._outputs[output.pk] = cast(
                OutputTrailSpec,
                load_trail("output", output.fingerprint, OutputTrailSpec),
            )

        return self._outputs[output.pk]

    def case_of(self, run: RunModel) -> str | None:
        """The run's case, by its name in the inventory: the archive's."""
        case_id = run.trial.case_id

        if case_id not in self._cases:
            self._cases[case_id] = (
                CaseBranchModel.objects.filter(
                    owner__name=settings.ARCHIVE_IDENTITY_NAME, target_id=case_id
                )
                .order_by("-timestamp", "-pk")
                .values_list("name", flat=True)
                .first()
            )

        return self._cases[case_id]


def latest(run: RunModel) -> list[ScoreModel]:
    """The run's latest score from each scorer, in the scorers' order."""
    found = {score.scorer: score for score in run.scores.all()}
    return [found[scorer.name] for scorer in SCORERS if scorer.name in found]

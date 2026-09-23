# pyright: basic
"""
What a batch stands for, and what it makes.

A batch names an agent, a set of case tags and a set of scorers. The
experiments it stands for are every pairing of a case carrying one of those
tags with an expectation of that case whose scorer was asked for, and can
judge what the agent returns -- one experiment per (case, expectation), all
of them running the batch's agent.

`plan` works that set out without writing anything, so the numbers can be
shown before the user commits to them; `generate` is the same walk, written
down. A batch keeps the order rather than its outcome, so `generate` can be
called again (the re-queue button) for a second set of experiments from the
same order.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import TagModel
from chatddx.core.worker import wake_on_commit
from chatddx.django.orm.qs import qs_canon
from chatddx.eval.scorers import scorer_reads
from chatddx.history.models import BatchModel, ExperimentModel, RunModel
from chatddx.repo.entities.agent.django import AgentTrailModel
from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.scorer.django import ScorerBranchModel, ScorerTrailModel

# How many of the excluded cases a message names before it stops counting
# them out one by one.
EXCLUDED_SHOWN = 5


@dataclass(frozen=True)
class PlanRow:
    """How many experiments one tag/scorer pairing accounts for."""

    tag: str
    scorer: str
    count: int


@dataclass(frozen=True)
class BatchPlan:
    """
    The experiments a batch would generate, before any of them exist.

    `pairs` is what gets written -- one (case trail, expect trail) each --
    and `rows` is the same set counted per tag and scorer. A case carrying
    two of the batch's tags is counted under both, so the rows can add up to
    more than `total`; `overlapping` says when they do.

    `unreadable` names the scorers in play that cannot judge what the agent
    returns: the expectations they judge are left out, since every run of
    one would fail at scoring.
    """

    rows: tuple[PlanRow, ...]
    pairs: tuple[tuple[int, int], ...]
    excluded: tuple[str, ...]
    unreadable: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return len(self.pairs)

    @property
    def excluded_shown(self) -> tuple[str, ...]:
        return self.excluded[:EXCLUDED_SHOWN]

    @property
    def excluded_rest(self) -> int:
        return max(len(self.excluded) - EXCLUDED_SHOWN, 0)

    @property
    def overlapping(self) -> bool:
        return sum(row.count for row in self.rows) != self.total


def plan(
    owner_name: str,
    agent: AgentTrailModel,
    tags: Sequence[TagModel],
    scorers: Sequence[ScorerBranchModel],
) -> BatchPlan:
    """
    What generating for `owner_name` would produce, right now.

    Cases are the owner's canon ones carrying any of `tags`; expectations are
    theirs, narrowed to `scorers` where any were named and left whole where
    none were, and to the scorers that can judge what `agent` returns. A
    case that ends up with no expectation to run is excluded, and named in
    the plan so the user hears about it before generating.
    """
    tag_names = {tag.pk: tag.name for tag in tags}
    wanted = {scorer.target_id: scorer.name for scorer in scorers}
    reads = _Reads(agent)

    cases = (
        qs_canon(CaseBranchModel.objects.all(), owner_name)
        .filter(tags__in=list(tag_names))
        .distinct()
        .prefetch_related("tags", "expects__target__scorer")
    )

    counts: Counter[tuple[str, int]] = Counter()
    pairs: dict[tuple[int, int], None] = {}
    excluded: list[str] = []

    for case in cases:
        expects = [
            expect
            for expect in case.expects.all()
            if (not wanted or expect.target.scorer_id in wanted)
            and reads(expect.target.scorer)
        ]

        if not expects:
            excluded.append(case.name)
            continue

        case_tags = [
            tag_names[tag.pk] for tag in case.tags.all() if tag.pk in tag_names
        ]

        for expect in expects:
            pair = (case.target_id, expect.target_id)

            # Two cases of the owner's can stand for the same content, and
            # then for the same experiment; it is only ever made once.
            if pair in pairs:
                continue

            pairs[pair] = None

            for tag in case_tags:
                counts[(tag, expect.target.scorer_id)] += 1

    # A scorer that was asked for is named even when no case carries it:
    # asking for one that cannot read the agent's output is worth hearing.
    unreadable = reads.unreadable() | {
        scorer_id for scorer_id in wanted if not reads.by_id(scorer_id)
    }

    scorer_names = _scorer_names(
        owner_name,
        wanted,
        {scorer_id for _, scorer_id in counts} | unreadable,
    )

    return BatchPlan(
        rows=_rows(counts, tag_names, wanted, scorer_names),
        pairs=tuple(pairs),
        excluded=tuple(sorted(excluded)),
        unreadable=tuple(sorted(scorer_names[pk] for pk in unreadable)),
    )


def plan_for(batch: BatchModel) -> BatchPlan:
    return plan(
        batch.owner.name,
        batch.agent,
        list(batch.case_tags.all()),
        list(batch.scorers.all()),
    )


class _Reads:
    """
    Which scorers can judge what one agent returns, asked once per scorer.

    A scorer this code has no contract for is not ruled out: nothing says
    what it reads, and its runs fail at scoring with a message saying so.
    """

    def __init__(self, agent: AgentTrailModel):
        self.definition: dict[str, Any] = agent.output_type.definition
        self.verdicts: dict[int, bool] = {}

    def __call__(self, scorer: ScorerTrailModel) -> bool:
        if scorer.pk not in self.verdicts:
            self.verdicts[scorer.pk] = (
                scorer_reads(scorer.command, self.definition) is not False
            )

        return self.verdicts[scorer.pk]

    def by_id(self, scorer_id: int) -> bool:
        if scorer_id not in self.verdicts:
            return self(ScorerTrailModel.objects.get(pk=scorer_id))

        return self.verdicts[scorer_id]

    def unreadable(self) -> set[int]:
        return {pk for pk, readable in self.verdicts.items() if not readable}


@dataclass(frozen=True)
class Generated:
    """What one generation of a batch came to."""

    experiments: list[ExperimentModel]
    plan: BatchPlan


def generate(batch: BatchModel, status: str) -> Generated:
    """
    Write the batch's experiments down, each with a run of its own at
    `status`, and ring the worker's doorbell if those runs are queued.
    """
    plan_ = plan_for(batch)

    with transaction.atomic():
        experiments = ExperimentModel.objects.bulk_create(
            ExperimentModel(
                owner_id=batch.owner_id,
                agent_id=batch.agent_id,
                case_id=case_id,
                expect_id=expect_id,
                batch=batch,
            )
            for case_id, expect_id in plan_.pairs
        )

        RunModel.objects.bulk_create(
            RunModel(
                owner_id=batch.owner_id,
                experiment=experiment,
                status=status,
            )
            for experiment in experiments
        )

    if status == RunStatusChoices.QUEUED:
        wake_on_commit()

    return Generated(experiments=experiments, plan=plan_)


def _rows(
    counts: Counter[tuple[str, int]],
    tag_names: dict[int, str],
    wanted: dict[int, str],
    scorer_names: dict[int, str],
) -> tuple[PlanRow, ...]:
    """
    A row per tag and scorer, in name order.

    Named scorers each get a row whether or not anything came of them -- a
    zero is how the user sees that their cases carry no expectation for one,
    or none that one can judge. Where none were named the batch stands for
    whatever the cases carry, so only those scorers have a row.
    """
    scorer_ids = (
        sorted(wanted, key=lambda pk: scorer_names[pk])
        if wanted
        else sorted(
            {scorer_id for _, scorer_id in counts}, key=lambda pk: scorer_names[pk]
        )
    )

    return tuple(
        PlanRow(
            tag=tag,
            scorer=scorer_names[scorer_id],
            count=counts[(tag, scorer_id)],
        )
        for tag in sorted(tag_names.values())
        for scorer_id in scorer_ids
    )


def _scorer_names(
    owner_name: str,
    wanted: dict[int, str],
    in_play: Iterable[int],
) -> dict[int, str]:
    """
    What each scorer trail in play reads as: the name the owner's branch of
    it carries, and the trail's own short hash for one they have no branch of.
    """
    names = {
        branch.target_id: branch.name
        for branch in qs_canon(ScorerBranchModel.objects.all(), owner_name)
    } | wanted

    missing = set(in_play) - set(names)

    return names | {
        trail.pk: str(trail)
        for trail in ScorerTrailModel.objects.filter(pk__in=missing)
    }


def excluded_message(plan_: BatchPlan) -> str | None:
    """The exclusions as one line, for a message after the fact."""
    if not plan_.excluded:
        return None

    return (
        f"{len(plan_.excluded)} case(s) left out for want of a scorer that can "
        + "judge this agent's output: "
        + _names(plan_.excluded_shown, plan_.excluded_rest)
    )


def _names(shown: Iterable[str], rest: int) -> str:
    listed = ", ".join(shown)

    return f"{listed} and {rest} more." if rest else f"{listed}."

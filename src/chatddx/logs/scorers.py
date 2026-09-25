# pyright: basic
"""
The registry's scorers as inspect's, so that inspect scores a log as
chatddx scores its runs (chatddx.scoring): each runs its function, loaded as
chatddx loads it, on the view it names and the case's target of its kind,
both read from the sample's metadata. A scorer keeps its registry name, and
its function, view, target kind and arguments are its options, so the log
says what scored it; each score also keeps the target it was held to and
the blob of the file that scored.

Where chatddx makes no score, inspect's is unscored, which its metrics and
reducers leave out: for a run that errored, a case without the scorer's
kind of target, or an output without its view. So is one whose value
chatddx leaves empty, as `first_mention`'s where the target is never named,
with the same reason.
"""

from typing import Any

from inspect_ai import score
from inspect_ai.log import EvalLog
from inspect_ai.scorer import (
    Metric,
    Score,
    Scorer,
    Target,
    mean,
    scorer,
    std,
    stderr,
    var,
)
from inspect_ai.solver import TaskState

from chatddx.history.models import RunStatus
from chatddx.repo.entities.output.pydantic import View
from chatddx.repo.entities.scorer.pydantic import Metric as MetricName
from chatddx.runtime.implementation import SCORER_PACKAGE, implementation
from chatddx.scoring.score import Scoring, VisibleScorer

READS: tuple[View, ...] = ("differential", "text", "warning", "disposition")

METRICS: dict[MetricName, Metric] = {
    "mean": mean(),
    "stderr": stderr(),
    "std": std(),
    "var": var(),
}


def as_inspect(visible: VisibleScorer) -> Scorer:
    """The scorer, as inspect's, under its name."""

    @scorer(
        metrics=[METRICS[metric] for metric in visible.metrics],
        name=visible.name,
    )
    def registry_scorer(
        function: str,
        view: str,
        target_kind: str | None = None,
        args: dict[str, Any] | None = None,
    ) -> Scorer:
        ran = implementation(function, SCORER_PACKAGE)

        async def hold(state: TaskState, target: Target) -> Score:
            if state.metadata.get("status") != RunStatus.COMPLETED:
                return Score.unscored(reason="errored")

            views: dict[str, list[str]] | None = state.metadata.get("views")

            if views is not None and view not in views:
                return Score.unscored(reason=f"the output offers no {view}")

            targets: dict[str, Any] = state.metadata.get("targets") or {}

            if target_kind is not None and target_kind not in targets:
                return Score.unscored(reason=f"the case has no {target_kind} target")

            wanted = targets.get(target_kind) if target_kind else None
            held_to = wanted if isinstance(wanted, str) else None
            scored = ran.function(
                None if views is None else views[view], held_to, **(args or {})
            )
            metadata = {"target": held_to, "blob": ran.blob}

            if scored.value is None:
                return Score.unscored(
                    reason=scored.reason, answer=scored.answer, metadata=metadata
                )

            return Score(
                value=scored.value,
                answer=scored.answer,
                reason=scored.reason,
                metadata=metadata,
            )

        return hold

    return registry_scorer(
        function=visible.trail.function,
        view=visible.view,
        target_kind=visible.target_kind,
        args=visible.args,
    )


def scored(log: EvalLog, identity: str) -> EvalLog:
    """
    `log`, scored by the scorers `identity` sees whose view its output
    offers, as its metadata says, in place of any scores it had. They go in
    the order of the views they read, so that the log's headline is the
    diagnosis's rank where the output offers a differential.
    """
    offered = (log.eval.metadata or {}).get("views") or []
    scorers = [
        as_inspect(visible)
        for visible in sorted(
            Scoring(identity).scorers,
            key=lambda visible: (READS.index(visible.view), visible.name),
        )
        if visible.view in offered
    ]

    if not scorers:
        return log

    return score(
        log, scorers, model="none", action="overwrite", display="none", copy=False
    )

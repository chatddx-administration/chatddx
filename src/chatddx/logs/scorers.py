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
from chatddx.repo.entities.case.pydantic import pattern_of
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

            wanted = targets.get(target_kind) if target_kind else None
            held_to = pattern_of(wanted)

            if target_kind is not None and wanted is not False and held_to is None:
                return Score.unscored(reason=f"the case has no {target_kind} target")
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

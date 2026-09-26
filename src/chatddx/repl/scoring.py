from rich.table import Table

from chatddx.history.models import RunStatus, ScoreModel
from chatddx.repl.render import LABEL, show_scores, value_of
from chatddx.repl.reviewing import short, what_ran
from chatddx.repl.shell import Repl
from chatddx.repo.entities.scorer.pydantic import Metric
from chatddx.scoring.metrics import METRICS
from chatddx.scoring.score import Scoring


def score(repl: Repl, prefix: str | None = None) -> None:
    scoring = Scoring(repl.identity)

    if prefix is not None:
        run = repl.run_named(prefix)
        made = scoring.score(run)
        repl.console.print(f"run {short(run.uuid)}: {what_ran(run)}", style="bold")

        if made:
            show_scores(repl.console, made)
        elif run.status == RunStatus.ERRORED:
            repl.console.print("errored: nothing to score", style=LABEL)
        elif not scoring.applicable(run):
            repl.console.print("no scorer applies to it", style=LABEL)
        else:
            repl.console.print("scored already, as the scorers are now", style=LABEL)
            show_scores(repl.console, scoring.latest(run))

        return

    runs = scoring.outstanding_runs()

    if not runs:
        repl.console.print("nothing to score", style=LABEL)
        return

    made: list[ScoreModel] = []

    for run in runs:
        repl.console.print(f"run {short(run.uuid)}: {what_ran(run)}", style="bold")
        scored = scoring.score(run)
        show_scores(repl.console, scored)
        made += scored

    summary(repl, scoring, made)


def scorers(repl: Repl) -> None:
    scoring = Scoring(repl.identity)
    offered = repl.cell.slices.output.views if repl.cell.configuration else None
    table = Table(box=None, header_style="bold")

    for column in ("scorer", "function", "reads", "held to", "metrics", "owner"):
        table.add_column(column)

    if offered is not None:
        table.add_column("the cell")

    for scorer in scoring.scorers:
        row = [
            scorer.name,
            scorer.trail.function.partition(":")[2],
            scorer.view,
            scorer.target_kind or "—",
            " ".join(scorer.metrics),
            "" if scorer.owner == repl.identity else scorer.owner,
        ]

        if offered is not None:
            row.append("offers it" if scorer.view in offered else "—")

        table.add_row(*row)

    repl.console.print(table)


def summary(repl: Repl, scoring: Scoring, made: list[ScoreModel]) -> None:
    metrics: list[Metric] = [
        metric
        for metric in METRICS
        if any(metric in scorer.metrics for scorer in scoring.scorers)
    ]
    table = Table(box=None, header_style="bold")

    for column in ("scorer", "runs", *metrics, "without a value"):
        table.add_column(column)

    for summed in scoring.summed(made):
        table.add_row(
            summed.scorer.name,
            str(summed.scores),
            *(
                value_of(summed.metrics[metric]) if metric in summed.metrics else ""
                for metric in metrics
            ),
            str(summed.without) if summed.without else "",
        )

    repl.console.print(table)

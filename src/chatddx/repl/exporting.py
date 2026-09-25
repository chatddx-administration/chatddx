# pyright: basic
"""Your runs of the cell, written as an inspect log, and scored by inspect."""

from chatddx.history.models import RunModel
from chatddx.repl.render import LABEL
from chatddx.repl.shell import Repl
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailIn
from chatddx.repo.entities.stack.django import StackTrailModel


def export(repl: Repl, directory: str | None = None) -> None:
    """
    Write your runs of the cell as an inspect log, into DIRECTORY or where
    inspect looks for logs, scored by inspect with the scorers you see, for
    `inspect view` to show.
    """
    cell = repl.cell

    if not (cell.configuration and cell.stack):
        repl.error(
            "the cell needs a configuration and a stack: cell CONFIGURATION STACK"
        )
        return

    fingerprint = ConfigurationTrailIn.model_validate(
        cell.slices, from_attributes=True
    ).fingerprint

    if not RunModel.objects.filter(
        owner__name=repl.identity,
        trial__configuration__fingerprint=fingerprint,
        trial__stack=cell.stack.trail.id,
    ).exists():
        repl.error(f"{repl.identity} has no runs of the cell")
        return

    # inspect takes seconds to load, and only a log needs it
    from chatddx.logs.export import cell_log, write
    from chatddx.logs.scorers import scored

    log = scored(
        cell_log(
            repl.identity,
            ConfigurationTrailModel.objects.get(fingerprint=fingerprint),
            StackTrailModel.objects.get(pk=cell.stack.trail.id),
            cell.label,
        ),
        repl.identity,
    )
    path = write(log, directory)
    samples = log.samples or []
    cases = len({sample.id for sample in samples})
    epochs = max(sample.epoch for sample in samples)

    repl.console.print(
        f"{len(samples)} sample{'s' if len(samples) > 1 else ''} of"
        + f" {cases} case{'s' if cases > 1 else ''}, in up to {epochs}"
        + f" epoch{'s' if epochs > 1 else ''}: {path}"
    )

    if log.eval.scorers:
        scorers = ", ".join(scorer.name for scorer in log.eval.scorers)
        repl.console.print(f"scored by {scorers}", style=LABEL)

    repl.console.print(f"to see it: inspect view --log-dir {path.parent}", style=LABEL)

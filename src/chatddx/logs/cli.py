"""
`chatddx agreement FIRST SECOND LOG...`: how two scorers read the same
samples of inspect logs. inspect is loaded when the command runs, not when
`chatddx` starts.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table


def agreement(
    first: Annotated[str, typer.Argument(help="a scorer the logs hold scores of")],
    second: Annotated[str, typer.Argument(help="another")],
    logs: Annotated[
        list[Path],
        typer.Argument(exists=True, help="logs, or directories of logs"),
    ],
):
    """How two scorers read the same samples, and where they differ."""
    from inspect_ai.log import read_eval_log

    from chatddx.logs.agreement import agreement as measure

    paths = [
        found
        for path in logs
        for found in (sorted(path.glob("*.eval")) if path.is_dir() else [path])
    ]
    measured = measure((read_eval_log(str(path)) for path in paths), first, second)
    console = Console()

    if not measured.samples:
        console.print(f"no sample was scored by both {first} and {second}")
        raise typer.Exit(1)

    kappa = measured.kappa
    counts = Table(box=None, show_header=False)

    for what, count in (
        ("found by both", measured.both),
        ("by neither", measured.neither),
        (f"by {first} alone", measured.first_only),
        (f"by {second} alone", measured.second_only),
        ("scored the same", measured.same),
        ("kappa on found", "—" if kappa is None else f"{kappa:.2f}"),
    ):
        counts.add_row(what, str(count))

    console.print(f"{first} and {second}, over {measured.samples} samples")
    console.print(counts)

    if not measured.disagreements:
        return

    differ = Table(box=None, header_style="bold")

    for column in ("task", "sample", "epoch", first, second):
        differ.add_column(column)

    for disagreement in measured.disagreements:
        differ.add_row(
            disagreement.task,
            str(disagreement.sample),
            str(disagreement.epoch),
            *(
                f"{value:g} {answer or ''}".strip()
                for value, answer in zip(
                    disagreement.values, disagreement.answers, strict=True
                )
            ),
        )

    console.print("where they differ:")
    console.print(differ)

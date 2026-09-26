from typing import Any

from rich.table import Table
from rich.text import Text

from chatddx.bench.bench import SHARED_BY
from chatddx.bench.cell import SLICES
from chatddx.repl.render import LABEL
from chatddx.repl.shell import Repl
from chatddx.repo.store.branch import select_visible_branch_models


def configurations(repl: Repl) -> None:
    table = Table(box=None, header_style="bold")

    for column in ("configuration", *SLICES, "owner"):
        table.add_column(column)

    for model in select_visible_branch_models(
        "configuration", repl.identity, SHARED_BY["configuration"]
    ):
        trail: Any = model.trail
        slices = [repl.name_of(entity, getattr(trail, entity)) for entity in SLICES]
        table.add_row(model.name, *slices, _owner(repl, model.owner.name))

    repl.console.print(table)


def stacks(repl: Repl) -> None:
    table = Table(box=None, header_style="bold")

    for column in ("stack", "llm", "machine", "endpoint", "owner"):
        table.add_column(column)

    for spec in repl.stacks():
        table.add_row(
            spec.name,
            repl.name_of("llm", spec.trail.llm),
            repl.name_of("machine", spec.trail.machine),
            str(spec.details.endpoint or "—"),
            _owner(repl, spec.owner.name),
        )

    repl.console.print(table)


def cases(repl: Repl) -> None:
    names = repl.names("case")
    repl.console.print(Text("  ".join(names)))
    repl.console.print(f"{len(names)} cases", style=LABEL)


def _owner(repl: Repl, name: str) -> str:
    return "" if name == repl.identity else name

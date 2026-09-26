from rich.text import Text

from chatddx.bench.cell import NONE, SLICES
from chatddx.repl.render import LABEL
from chatddx.repl.shell import Repl
from chatddx.repo.names import short_fingerprint


def use(repl: Repl, name: str) -> None:
    repl.cell = repl.cell.using(repl.configuration_named(name), repl.called(name))
    repl.say_cell()


def on(repl: Repl, name: str) -> None:
    repl.cell = repl.cell.on(repl.stack_named(name))
    repl.say_cell()


def cell(repl: Repl, configuration: str, stack: str) -> None:
    """Both, each looked up before either is put in the cell."""
    repl.cell = repl.cell_of(configuration, stack)
    repl.say_cell()


def set_(repl: Repl, entity: str, name: str) -> None:
    cell = repl.cell

    if entity not in SLICES:
        repl.error(f"no slice '{entity}': {', '.join(SLICES)}")
        return

    if not cell.configuration:
        repl.error("the cell has no configuration to set it in: use CONFIGURATION")
        return

    try:
        repl.cell = cell.set(
            entity, None if name == NONE else repl.variation_named(entity, name)
        )
    except ValueError as e:
        repl.error(str(e))
        return

    repl.say_cell()


def save(repl: Repl, name: str) -> None:
    if not repl.cell.configuration:
        repl.error("the cell has no configuration to save: use CONFIGURATION")
        return

    try:
        saved = repl.save(repl.cell, name)
    except ValueError as e:
        repl.error(str(e))
        return

    repl.cell = saved.cell
    repl.console.print(
        f"saved as {name}: {saved.what} {short_fingerprint(saved.fingerprint)}"
    )

    if saved.copied:
        repl.console.print(
            Text(f"yours now too: {', '.join(saved.copied)}", style=LABEL)
        )

    repl.say_cell()

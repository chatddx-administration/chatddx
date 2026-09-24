"""Each command, the words it takes, what it does, and a line carried out."""

import shlex
from collections.abc import Callable
from dataclasses import dataclass

from rich.table import Table

from chatddx.core.repl import choosing, inspecting, listing, reviewing, running
from chatddx.core.repl.cell import NONE, OPTIONAL, SLICES
from chatddx.core.repl.shell import Repl
from chatddx.repo.shufflers.branch import AmbiguousBranchError, BranchNotFoundError


@dataclass(frozen=True)
class Command:
    """
    The words a command takes, a word in brackets optional, and what it
    does. One that runs nothing leaves the repl.
    """

    params: tuple[str, ...]
    text: str
    run: Callable[..., None] | None


def help_(repl: Repl) -> None:
    table = Table(box=None, show_header=False)

    for verb, command in COMMANDS.items():
        table.add_row(" ".join((verb, *command.params)), command.text)

    repl.console.print(table)


COMMANDS: dict[str, Command] = {
    "configurations": Command(
        (), "list the configurations you can use", listing.configurations
    ),
    "stacks": Command((), "list the stacks you can run on", listing.stacks),
    "cases": Command((), "list the cases you can run", listing.cases),
    "use": Command(
        ("CONFIGURATION",),
        "put a configuration in the cell: yours, the archive's, or OWNER/NAME",
        choosing.use,
    ),
    "on": Command(("STACK",), "put a stack in the cell", choosing.on),
    "cell": Command(("CONFIGURATION", "STACK"), "put both in the cell", choosing.cell),
    "set": Command(
        ("SLICE", "VARIATION"),
        "put another variation of a slice in the cell; none takes the toolset out",
        choosing.set_,
    ),
    "show": Command(
        (), "show the cell, and how it resolves on its stack", inspecting.show
    ),
    "reasoning": Command(
        (),
        "show what each reasoning variation does on each stack",
        inspecting.reasoning,
    ),
    "run": Command(
        ("CASE", "[SEED]"),
        "run a case on the cell, with a seed if given",
        running.run,
    ),
    "save": Command(
        ("NAME",), "save the cell's configuration as your own, as NAME", choosing.save
    ),
    "runs": Command(
        ("[COUNT]",),
        "list your latest runs, the last 20 unless COUNT says",
        reviewing.runs,
    ),
    "replay": Command(
        ("[RUN]",),
        "show a run again as it streamed: the latest, or RUN",
        reviewing.replay,
    ),
    "help": Command((), "list the commands", help_),
    "quit": Command((), "leave (or Ctrl-D)", None),
}


def handle(repl: Repl, line: str) -> bool:
    """Carry out one line; False when it asks to leave."""
    try:
        words = shlex.split(line)
    except ValueError as e:
        repl.error(str(e))
        return True

    if not words:
        return True

    verb, *args = words
    command = COMMANDS.get("quit" if verb == "exit" else verb)

    if command is None:
        repl.error(f"no command '{verb}': try help")
        return True

    if command.run is None:
        return False

    required = [param for param in command.params if not param.startswith("[")]

    if not len(required) <= len(args) <= len(command.params):
        repl.error(f"usage: {' '.join((verb, *command.params))}")
        return True

    try:
        command.run(repl, *args)
    except (BranchNotFoundError, AmbiguousBranchError) as e:
        repl.error(str(e))

    return True


def complete(names: dict[str, list[str]], line: str) -> list[str]:
    """What the last word of `line` can be: a command, then the names it takes."""
    verb, *words = line.split(" ")

    if not words:
        return [name for name in COMMANDS if name.startswith(verb)]

    command = COMMANDS.get(verb)
    params = command.params if command else ()
    position = len(words) - 1

    if position >= len(params):
        return []

    match params[position]:
        case "SLICE":
            candidates = list(SLICES)
        case "VARIATION":
            entity = words[position - 1]
            candidates = names.get(entity, []) + ([NONE] if entity in OPTIONAL else [])
        case param:
            candidates = names.get(param.lower(), [])

    return [name for name in candidates if name.startswith(words[-1])]

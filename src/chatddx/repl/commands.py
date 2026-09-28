import shlex
from collections.abc import Callable
from dataclasses import dataclass

from django import db
from rich.table import Table

from chatddx.bench.bench import NotFound
from chatddx.bench.cell import NONE, OPTIONAL, SLICES
from chatddx.repl import (
    choosing,
    inspecting,
    listing,
    reviewing,
    running,
    scoring,
)
from chatddx.repl.shell import Repl
from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.repo.store.branch import AmbiguousBranchError, BranchNotFoundError


@dataclass(frozen=True)
class Command:
    params: tuple[str, ...]
    text: str
    run: Callable[..., None] | None

    @property
    def repeats(self) -> bool:
        return bool(self.params) and self.params[-1].strip("[]").endswith("...")


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
        ("[ENTITY]", "[NAME...]"),
        "show the cell, how it resolves on its stack, and the cases each scorer"
        + " can hold it to (tag TAG...: those with any TAG); or an ENTITY, the"
        + " cell's or NAME, and what came of your runs with it",
        inspecting.show,
    ),
    "reasoning": Command(
        (),
        "show what each reasoning variation does on each stack",
        inspecting.reasoning,
    ),
    "run": Command(
        ("CASE", "[SEED]"),
        "run a case on the cell, with SEED or the seed the repl holds",
        running.run,
    ),
    "seed": Command(
        ("[SEED]",),
        "draw a fresh seed for run and batch; SEED holds it, none runs unseeded",
        running.seed,
    ),
    "batch": Command(
        ("TAG...",),
        "run the cell on each case with any TAG, one after another (Ctrl-C stops)",
        running.batch,
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
    "score": Command(
        ("[RUN]",),
        "hold your outstanding runs, or RUN, to the scorers that apply",
        scoring.score,
    ),
    "scorers": Command(
        (),
        "list the scorers, what each reads, and which the cell's output offers",
        scoring.scorers,
    ),
    "help": Command((), "list the commands", help_),
    "quit": Command((), "leave (or Ctrl-D)", None),
}


def handle(repl: Repl, line: str) -> bool:
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
    most = len(args) if command.repeats else len(command.params)

    if not len(required) <= len(args) <= most:
        repl.error(f"usage: {' '.join((verb, *command.params))}")
        return True

    try:
        command.run(repl, *args)
    except (BranchNotFoundError, AmbiguousBranchError, NotFound) as e:
        repl.error(str(e))
    except db.Error as e:
        said = str(e).strip()
        repl.error(
            f"the database failed: {said.splitlines()[0] if said else type(e).__name__}"
        )

    return True


def complete(names: dict[str, list[str]], line: str) -> list[str]:
    verb, *words = line.split(" ")

    if not words:
        return [name for name in COMMANDS if name.startswith(verb)]

    command = COMMANDS.get(verb)
    params = command.params if command else ()
    position = len(words) - 1
    given: list[str] = []

    if command and command.repeats and position >= len(params) - 1:
        position = len(params) - 1
        given = words[position:-1]
    elif position >= len(params):
        return []

    match params[position]:
        case "SLICE":
            candidates = list(SLICES)
        case "VARIATION":
            entity = words[position - 1]
            candidates = names.get(entity, []) + ([NONE] if entity in OPTIONAL else [])
        case "[ENTITY]":
            candidates = ["tag", *ENTITY_NAMES]
        case "[NAME...]" if words[0] == "tag":
            candidates = names.get("batch:tag", [])
        case "[NAME...]":
            candidates = [] if given else names.get(words[0], [])
        case param:
            key = param.strip("[].").lower()
            candidates = names.get(f"{verb}:{key}", names.get(key, []))

    return [
        name for name in candidates if name.startswith(words[-1]) and name not in given
    ]

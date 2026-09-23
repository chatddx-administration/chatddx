# pyright: basic
"""
The repl: run cases on a cell, and watch the model answer as it goes.

A cell is a configuration joined to a stack (new-datamodel.md §5), and the
repl holds one the way psql holds a database: `use` puts a configuration in
it, `on` a stack, and `run` makes a trial of it on a case. Names are looked
up as the identity the repl runs as sees them: its own branches first, then
those shared with it.
"""

import asyncio
import json
import logging
import readline
import shlex
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import JsonValue
from pydantic_ai import (
    AgentRunEvents,
    AgentRunResultEvent,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
)
from rich.console import Console
from rich.table import Table
from rich.text import Text

from chatddx.core.models import IdentityModel
from chatddx.repo.entities.configuration.pydantic import ConfigurationBranchSpec
from chatddx.repo.entities.model.pydantic import ModelBranchSpec, ModelFacts
from chatddx.repo.entities.stack.pydantic import StackBranchSpec
from chatddx.repo.entity_names import EntityName
from chatddx.repo.names import short_fingerprint
from chatddx.repo.shufflers.branch import (
    AmbiguousBranchError,
    BranchNotFoundError,
    get_visible_branch_model,
    select_visible_branch_models,
)
from chatddx.runtime.resolution import (
    CellRefused,
    Reasoning,
    Resolution,
    Sampling,
    SliceRefusal,
    resolve,
)
from chatddx.runtime.trial import Trial

HISTORY = Path.home() / ".chatddx_history"

THINKING = "#5f87af"
LABEL = "dim"
REFUSED = "red"
LATER = "yellow"

# what each command takes, and what it does
COMMANDS: dict[str, tuple[tuple[str, ...], str]] = {
    "configurations": ((), "list the configurations you can use"),
    "stacks": ((), "list the stacks you can run on"),
    "cases": ((), "list the cases you can run"),
    "use": (("CONFIGURATION",), "put a configuration in the cell"),
    "on": (("STACK",), "put a stack in the cell"),
    "cell": (("CONFIGURATION", "STACK"), "put both in the cell"),
    "show": ((), "show the cell, and how it resolves on its stack"),
    "run": (("CASE",), "run a case on the cell"),
    "help": ((), "list the commands"),
    "quit": ((), "leave (or Ctrl-D)"),
}

SLICES: tuple[EntityName, ...] = (
    "instruction",
    "output",
    "coercion",
    "reasoning",
    "sampling",
    "toolset",
)


class Repl:
    def __init__(
        self,
        identity_name: str,
        console: Console,
        transport: Any = None,
    ):
        self.identity: str = identity_name
        self.console: Console = console
        # where trials are sent instead of the stack's endpoint: a fake vLLM
        self.transport: Any = transport

        self.configuration: ConfigurationBranchSpec | None = None
        self.stack: StackBranchSpec | None = None
        self.model: ModelBranchSpec | None = None

        self._names: dict[tuple[EntityName, int], str] = {}

    @property
    def prompt(self) -> str:
        configuration = self.configuration.name if self.configuration else ""
        stack = f"×{self.stack.name}" if self.stack else ""
        cell = f" {configuration}{stack}" if configuration or stack else ""
        return f"{self.identity}{cell}> "

    def handle(self, line: str) -> bool:
        """Carry out one line; False when it asks to leave."""
        try:
            words = shlex.split(line)
        except ValueError as e:
            self.error(str(e))
            return True

        if not words:
            return True

        verb, *args = words

        if verb in ("quit", "exit"):
            return False

        if verb not in COMMANDS:
            self.error(f"no command '{verb}': try help")
            return True

        params, _ = COMMANDS[verb]

        if len(args) != len(params):
            self.error(f"usage: {' '.join((verb, *params))}")
            return True

        try:
            getattr(self, f"do_{verb}")(*args)
        except (BranchNotFoundError, AmbiguousBranchError) as e:
            self.error(str(e))

        return True

    def names(self, entity: EntityName) -> list[str]:
        return sorted(
            {m.name for m in select_visible_branch_models(entity, self.identity)}
        )

    # ------------------------------------------------------------- commands

    def do_help(self) -> None:
        table = Table(box=None, show_header=False)

        for verb, (params, text) in COMMANDS.items():
            table.add_row(" ".join((verb, *params)), text)

        self.console.print(table)

    def do_configurations(self) -> None:
        table = Table(box=None, header_style="bold")

        for column in ("configuration", *SLICES, "owner"):
            table.add_column(column)

        for model in select_visible_branch_models("configuration", self.identity):
            trail: Any = model.target
            slices = [self.name_of(entity, getattr(trail, entity)) for entity in SLICES]
            table.add_row(model.name, *slices, self.owner(model.owner.name))

        self.console.print(table)

    def do_stacks(self) -> None:
        table = Table(box=None, header_style="bold")

        for column in ("stack", "model", "machine", "endpoint", "owner"):
            table.add_column(column)

        for model in select_visible_branch_models("stack", self.identity):
            spec = StackBranchSpec.model_validate(model)
            table.add_row(
                spec.name,
                self.name_of("model", spec.target.model),
                self.name_of("machine", spec.target.machine),
                str(spec.details.endpoint or "—"),
                self.owner(spec.owner.name),
            )

        self.console.print(table)

    def do_cases(self) -> None:
        names = self.names("case")
        self.console.print(Text("  ".join(names)))
        self.console.print(f"{len(names)} cases", style=LABEL)

    def do_use(self, name: str) -> None:
        model = get_visible_branch_model("configuration", self.identity, name)
        self.configuration = ConfigurationBranchSpec.model_validate(model)
        self.say_cell()

    def do_on(self, name: str) -> None:
        self.put_stack(get_visible_branch_model("stack", self.identity, name))
        self.say_cell()

    def do_cell(self, configuration: str, stack: str) -> None:
        # both looked up before either is put in the cell
        configuration_model = get_visible_branch_model(
            "configuration", self.identity, configuration
        )
        stack_model = get_visible_branch_model("stack", self.identity, stack)

        self.configuration = ConfigurationBranchSpec.model_validate(configuration_model)
        self.put_stack(stack_model)
        self.say_cell()

    def do_show(self) -> None:
        if not (self.configuration or self.stack):
            self.error("the cell is empty: use CONFIGURATION, on STACK")
            return

        self.say_cell()

        refusals: list[SliceRefusal] = []
        resolution: Resolution | None = None
        parts: Parts | None = None

        if self.configuration and self.stack:
            try:
                resolution = self.resolve()
                parts = (resolution.reasoning, resolution.sampling, resolution.slots)
            except CellRefused as e:
                refusals = e.refusals
                parts = (e.reasoning, e.sampling, e.slots)

        table = Table(box=None, header_style="bold")
        table.add_column("slice")
        table.add_column("variation")
        table.add_column("on the stack" if self.stack else "")

        if self.stack:
            model = self.name_of("model", self.stack.target.model)
            where = f"{self.stack.details.served_name} at {self.stack.details.endpoint}"
            table.add_row("model", model, self.outcome("model", refusals, where))

        if self.configuration:
            trail = self.configuration.target

            for entity in SLICES:
                variation = getattr(trail, entity)
                name = self.name_of(entity, variation) if variation else "—"
                realized = _realized(entity, trail, parts) if parts else ""
                table.add_row(entity, name, self.outcome(entity, refusals, realized))

        self.console.print(table)

        if resolution:
            system, user = resolution.render("‹case›")
            self.console.print("system", style="bold")
            self.console.print(Text(system or "(none)"))
            self.console.print("user", style="bold")
            self.console.print(Text(user))

    def do_run(self, name: str) -> None:
        if not (self.configuration and self.stack):
            self.error(
                "the cell needs a configuration and a stack: cell CONFIGURATION STACK"
            )
            return

        try:
            resolution = self.resolve()
        except CellRefused as e:
            self.say_refusals(e.refusals)
            return

        case = get_visible_branch_model("case", self.identity, name)
        api_key = self.secret(resolution.credential)

        if resolution.credential and api_key is None:
            self.error(f"{self.identity} has no secret '{resolution.credential}'")
            return

        self.console.print(
            f"trial: {self.configuration.name} × {self.stack.name} × {case.name}",
            style="bold",
        )

        trial = Trial(
            resolution,
            case.target.payload,
            api_key=api_key,
            transport=self.transport,
        )

        try:
            asyncio.run(self.stream(trial))
        except KeyboardInterrupt:
            self.console.print("\n(stopped)", style=LABEL)
        except Exception as e:  # noqa: BLE001
            # the model or its server failed mid-run: say so and carry on
            self.error(f"\n{type(e).__name__}: {e}")

    # -------------------------------------------------------------- helpers

    def put_stack(self, model: Any) -> None:
        self.stack = StackBranchSpec.model_validate(model)

        try:
            self.model = ModelBranchSpec.model_validate(
                get_visible_branch_model(
                    "model", self.identity, trail=self.stack.target.model.id
                )
            )
        except (BranchNotFoundError, AmbiguousBranchError):
            # no facts to read: resolution refuses for want of them
            self.model = None

    def resolve(self) -> Resolution:
        assert self.configuration and self.stack

        facts = self.model.details.facts if self.model else ModelFacts()

        return resolve(
            self.configuration.target,
            self.stack.details,
            facts,
            self.stack.target.serving,
        )

    async def stream(self, trial: Trial) -> None:
        async with trial.stream() as events:
            await show_events(self.console, events)

    def name_of(self, entity: EntityName, trail: Any) -> str:
        """What the identity calls `trail`, or its short fingerprint."""
        if trail is None:
            return "—"

        key = (entity, trail.id)

        if key not in self._names:
            try:
                name = get_visible_branch_model(
                    entity, self.identity, trail=trail.id
                ).name
            except (BranchNotFoundError, AmbiguousBranchError):
                name = short_fingerprint(trail.fingerprint)

            self._names[key] = name

        return self._names[key]

    def owner(self, name: str) -> str:
        return "" if name == self.identity else name

    def secret(self, name: str | None) -> str | None:
        if name is None:
            return None

        identity = IdentityModel.objects.get(name=self.identity)
        secret = identity.secrets.get(name)

        return secret if isinstance(secret, str) else None

    def outcome(self, entity: str, refusals: list[SliceRefusal], realized: str) -> Text:
        mine = [r for r in refusals if r.slice == entity]

        if not mine:
            return Text(realized)

        text = Text()

        for i, refusal in enumerate(mine):
            if i:
                text.append("\n")
            if refusal.kind == "later":
                text.append(f"not yet: {refusal.reason}", style=LATER)
            else:
                text.append(f"refused: {refusal.reason}", style=REFUSED)

        return text

    def say_cell(self) -> None:
        configuration = self.configuration.name if self.configuration else "?"
        stack = self.stack.name if self.stack else "?"
        self.console.print(f"cell: {configuration} × {stack}")

    def say_refusals(self, refusals: Iterable[SliceRefusal]) -> None:
        for refusal in refusals:
            if refusal.kind == "later":
                self.console.print(
                    Text(f"not yet: {refusal.slice}: {refusal.reason}", style=LATER)
                )
            else:
                self.console.print(
                    Text(f"refused: {refusal.slice}: {refusal.reason}", style=REFUSED)
                )

    def error(self, message: str) -> None:
        self.console.print(Text(message, style=REFUSED))


# what the slices resolved to, whether or not the cell is refused
type Parts = tuple[Reasoning | None, Sampling | None, dict[str, str]]


def _realized(entity: str, configuration: Any, parts: Parts) -> str:
    reasoning, sampling, slots = parts
    free_text = configuration.output.schema is None

    match entity:
        case "reasoning" if reasoning:
            writes = _writes(reasoning.writes)
            if reasoning.effort == "default":
                return f"the model's default, '{reasoning.intent}': {writes}"
            if reasoning.effort != reasoning.intent:
                return f"collapses into '{reasoning.intent}': {writes}"
            return writes
        case "sampling" if sampling:
            return f"{sampling.source}: {_writes(sampling.writes) or 'nothing'}"
        case "output" if free_text:
            return "free text"
        case "coercion" if free_text:
            return "nothing to coerce in free text"
        case "instruction":
            return f"filled: {', '.join(slots) or 'no slots'}"
        case _:
            return ""


def _writes(writes: dict[str, JsonValue]) -> str:
    return " ".join(f"{k}={json.dumps(v)}" for k, v in writes.items())


async def show_events(console: Console, events: AgentRunEvents[str]) -> None:
    """Write out a trial's events as they come: its thinking, then its answer."""
    at_start = True

    def write(text: str, style: str = "") -> None:
        nonlocal at_start
        if text:
            console.out(text, style=style or None, end="", highlight=False)
            at_start = text.endswith("\n")

    def begin(label: str | None) -> None:
        nonlocal at_start
        if not at_start:
            console.out("")
            at_start = True
        if label:
            console.out(f"[{label}] ", style=LABEL, end="", highlight=False)
            at_start = False

    async for event in events:
        match event:
            case PartStartEvent(part=ThinkingPart(content=text)):
                begin("thinking")
                write(text, THINKING)
            case PartDeltaEvent(delta=ThinkingPartDelta(content_delta=text)) if text:
                write(text, THINKING)
            case PartStartEvent(part=TextPart(content=text)):
                begin(None)
                write(text)
            case PartDeltaEvent(delta=TextPartDelta(content_delta=text)):
                write(text)
            case PartEndEvent():
                begin(None)
            case AgentRunResultEvent(result=result):
                usage = result.usage
                begin(None)
                console.out(
                    f"({usage.input_tokens} in, {usage.output_tokens} out)",
                    style=LABEL,
                    highlight=False,
                )
            case _:
                pass


def complete(names: dict[str, list[str]], line: str) -> list[str]:
    """What the last word of `line` can be: a command, then the names it takes."""
    verb, *words = line.split(" ")

    if not words:
        return [command for command in COMMANDS if command.startswith(verb)]

    params = COMMANDS.get(verb, ((), ""))[0]
    position = len(words) - 1

    if position >= len(params):
        return []

    return [
        name
        for name in names.get(params[position].lower(), [])
        if name.startswith(words[-1])
    ]


def repl(
    identity_name: Annotated[str, typer.Argument()],
    history: Annotated[
        Path,
        typer.Option(help="where the lines you type are kept"),
    ] = HISTORY,
):
    """Run cases on a configuration and a stack."""
    if not IdentityModel.objects.filter(name=identity_name).exists():
        typer.echo(
            f"no identity '{identity_name}': chatddx init-data {identity_name}",
            err=True,
        )
        raise typer.Exit(1)

    # a line per request would break into the answer as it streams
    for logger in ("httpx", "httpx2"):
        logging.getLogger(logger).setLevel(logging.WARNING)

    shell = Repl(identity_name, Console())

    # looked up once: a name is completed from these as it is typed
    names = {
        entity: shell.names(entity) for entity in ("configuration", "stack", "case")
    }

    def completer(_word: str, state: int) -> str | None:
        line = readline.get_line_buffer()[: readline.get_endidx()]
        matches = complete(names, line)
        # the space readline leaves out, so the next word can follow
        return f"{matches[state]} " if state < len(matches) else None

    readline.set_completer(completer)
    # names hold `-`, `@` and `.`: only a space ends a word
    readline.set_completer_delims(" ")
    readline.parse_and_bind("tab: complete")

    try:
        readline.read_history_file(history)
    except OSError:
        pass

    # piped in, a line is echoed after the prompt, as if it was typed
    interactive = sys.stdin.isatty()

    try:
        while True:
            try:
                line = input(shell.prompt)
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                print()
                break

            if not interactive:
                print(line)

            if not shell.handle(line):
                break
    finally:
        try:
            readline.write_history_file(history)
        except OSError:
            pass

# pyright: basic
"""
The repl: run cases on a cell, and watch the model answer as it goes.

A cell is a configuration joined to a stack (new-datamodel.md §5), and the
repl holds one the way psql holds a database: `use` puts a configuration in
it, `on` a stack, `set` another variation of one of its slices, and `run`
makes a trial of it on a case. Names are looked up as the identity the repl
runs as sees them: its own branches first, then those shared with it.

Every run is recorded: `runs` lists them, and `replay` shows one again as it
streamed. `save` keeps the cell as a configuration of the identity's own.
"""

import asyncio
import json
import logging
import readline
import shlex
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, cast, get_args

import typer
from django.db import transaction
from django.utils import timezone
from pydantic import JsonValue
from pydantic_ai import (
    AgentRunEvents,
    AgentRunResultEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
    ToolReturnPart,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from rich.console import Console
from rich.table import Table
from rich.text import Text

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.history.models import MessageKind, RunModel, RunStatus
from chatddx.history.record import Branches, Outcome, record
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.coercion.pydantic import SLOT as SCHEMA_PROMPT
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchSpec,
    ConfigurationTrailSchema,
)
from chatddx.repo.entities.model.pydantic import ModelBranchSpec, ModelFacts
from chatddx.repo.entities.output.pydantic import OutputTrailBase, OutputTrailSpec
from chatddx.repo.entities.reasoning.pydantic import Effort, ReasoningBranchSpec
from chatddx.repo.entities.stack.pydantic import StackBranchSpec
from chatddx.repo.entities.tool.pydantic import ToolBranchSpec
from chatddx.repo.entity_names import EntityName
from chatddx.repo.names import short_fingerprint
from chatddx.repo.shufflers.branch import (
    AmbiguousBranchError,
    BranchNotFoundError,
    commit,
    commit_copies,
    get_branch_model,
    get_visible_branch_model,
    select_visible_branch_models,
)
from chatddx.repo.shufflers.trail import dump_trail, load_trail
from chatddx.runtime.resolution import (
    CellRefused,
    Coercion,
    Reasoning,
    Resolution,
    Sampling,
    SliceRefusal,
    Slices,
    Tool,
    realize,
    resolve,
)
from chatddx.runtime.trial import (
    FINAL_RESULT,
    TOOL_ROUNDS,
    Trial,
    cause_of,
    invalid,
)

HISTORY = Path.home() / ".chatddx_history"

THINKING = "#5f87af"
LABEL = "dim"
REFUSED = "red"
VALID = "green"
LATER = "yellow"

# what each command takes, and what it does
COMMANDS: dict[str, tuple[tuple[str, ...], str]] = {
    "configurations": ((), "list the configurations you can use"),
    "stacks": ((), "list the stacks you can run on"),
    "cases": ((), "list the cases you can run"),
    "use": (("CONFIGURATION",), "put a configuration in the cell"),
    "on": (("STACK",), "put a stack in the cell"),
    "cell": (("CONFIGURATION", "STACK"), "put both in the cell"),
    "set": (
        ("SLICE", "VARIATION"),
        "put another variation of a slice in the cell; none takes the toolset out",
    ),
    "show": ((), "show the cell, and how it resolves on its stack"),
    "reasoning": ((), "show what each reasoning variation does on each stack"),
    "run": (("CASE", "[SEED]"), "run a case on the cell, with a seed if given"),
    "save": (("NAME",), "save the cell's configuration as your own, as NAME"),
    "runs": (("[COUNT]",), "list your latest runs, the last 20 unless COUNT says"),
    "replay": (("[RUN]",), "show a run again as it streamed: the latest, or RUN"),
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

# Who a branch is looked for from, beside the identity: a configuration runs
# from the identity's own or the archive's, and one another user shares is
# saved as the identity's own before it can run.
SHARED_BY: dict[str, str] = {"configuration": settings.ARCHIVE_IDENTITY_NAME}

# the slices a configuration can do without, and the word that takes one out
OPTIONAL: tuple[EntityName, ...] = ("toolset",)
NONE = "none"

EFFORTS: tuple[Effort, ...] = get_args(Effort.__value__)


@dataclass(frozen=True)
class Streamed:
    answer: Any
    # whether any of the model's thinking came back
    thought: bool


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
        # the variations `set` put in the cell in place of the configuration's;
        # None where it took an optional slice out
        self.variations: dict[str, Any] = {}
        self.stack: StackBranchSpec | None = None

        self._names: dict[tuple[EntityName, int], str] = {}
        # a model's facts, by its trail, and the branch row they were read from
        self._models: dict[int, tuple[ModelFacts, int | None]] = {}
        # the names a command's words complete from, until one is saved
        self._completions: dict[str, list[str]] | None = None

    @property
    def label(self) -> str:
        """The cell's configuration, and what is set in it."""
        if not self.configuration:
            return ""

        set_ = "".join(
            f"+{entity}={self.set_name(entity)}"
            for entity in SLICES
            if entity in self.variations
        )
        return f"{self.configuration.name}{set_}"

    def set_name(self, entity: str) -> str:
        """The name of the variation set in the cell, or none."""
        variation = self.variations[entity]
        return NONE if variation is None else variation.name

    @property
    def prompt(self) -> str:
        stack = f"×{self.stack.name}" if self.stack else ""
        cell = f" {self.label}{stack}" if self.configuration or self.stack else ""
        return f"{self.identity}{cell}> "

    @property
    def slices(self) -> Slices:
        """The cell's variations: those set, and the configuration's."""
        return Slices(**{entity: self.variation(entity) for entity in SLICES})

    def variation(self, entity: str) -> Any:
        assert self.configuration

        if entity in self.variations:
            variation = self.variations[entity]
            return None if variation is None else variation.target

        return getattr(self.configuration.target, entity)

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
        required = [param for param in params if not param.startswith("[")]

        if not len(required) <= len(args) <= len(params):
            self.error(f"usage: {' '.join((verb, *params))}")
            return True

        try:
            getattr(self, f"do_{verb}")(*args)
        except (BranchNotFoundError, AmbiguousBranchError) as e:
            self.error(str(e))

        return True

    def completions(self) -> dict[str, list[str]]:
        """The names a command's words complete from, looked up once."""
        if self._completions is None:
            self._completions = {
                entity: self.names(entity)
                for entity in ("configuration", "stack", "case", *SLICES)
            }

        return self._completions

    def names(self, entity: EntityName) -> list[str]:
        models = select_visible_branch_models(
            entity, self.identity, SHARED_BY.get(entity)
        )
        return sorted({model.name for model in models})

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

        for model in select_visible_branch_models(
            "configuration", self.identity, SHARED_BY["configuration"]
        ):
            trail: Any = model.target
            slices = [self.name_of(entity, getattr(trail, entity)) for entity in SLICES]
            table.add_row(model.name, *slices, self.owner(model.owner.name))

        self.console.print(table)

    def do_stacks(self) -> None:
        table = Table(box=None, header_style="bold")

        for column in ("stack", "model", "machine", "endpoint", "owner"):
            table.add_column(column)

        for spec in self.stacks():
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
        model = get_visible_branch_model(
            "configuration", self.identity, name, shared_by=SHARED_BY["configuration"]
        )
        self.put_configuration(model)
        self.say_cell()

    def do_on(self, name: str) -> None:
        model = get_visible_branch_model("stack", self.identity, name)
        self.stack = StackBranchSpec.model_validate(model)
        self.say_cell()

    def do_cell(self, configuration: str, stack: str) -> None:
        # both looked up before either is put in the cell
        configuration_model = get_visible_branch_model(
            "configuration",
            self.identity,
            configuration,
            shared_by=SHARED_BY["configuration"],
        )
        stack_model = get_visible_branch_model("stack", self.identity, stack)

        self.put_configuration(configuration_model)
        self.stack = StackBranchSpec.model_validate(stack_model)
        self.say_cell()

    def do_set(self, entity: str, name: str) -> None:
        if entity not in SLICES:
            self.error(f"no slice '{entity}': {', '.join(SLICES)}")
            return

        if not self.configuration:
            self.error("the cell has no configuration to set it in: use CONFIGURATION")
            return

        own = getattr(self.configuration.target, entity)

        if name == NONE:
            if entity not in OPTIONAL:
                self.error(
                    f"a configuration always has a {entity}: only a toolset can be none"
                )
                return

            if own is None:
                _ = self.variations.pop(entity, None)
            else:
                self.variations[entity] = None

            self.say_cell()
            return

        model = get_visible_branch_model(entity, self.identity, name)
        spec = entity_of(entity).branch_spec.model_validate(model)

        if own is not None and own.fingerprint == spec.target.fingerprint:
            # the configuration's own: nothing is set any more
            _ = self.variations.pop(entity, None)
        else:
            self.variations[entity] = spec

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
                parts = (
                    resolution.reasoning,
                    resolution.sampling,
                    resolution.coercion,
                    resolution.tools,
                    resolution.slots,
                )
            except CellRefused as e:
                refusals = e.refusals
                parts = (e.reasoning, e.sampling, e.coercion, e.tools, e.slots)

        table = Table(box=None, header_style="bold")
        table.add_column("slice")
        table.add_column("variation")
        table.add_column("on the stack" if self.stack else "")

        if self.stack:
            model = self.name_of("model", self.stack.target.model)
            where = f"{self.stack.details.served_name} at {self.stack.details.endpoint}"
            table.add_row("model", model, self.outcome("model", refusals, where))

        if self.configuration:
            slices = self.slices

            for entity in SLICES:
                realized = _realized(entity, slices, parts) if parts else ""
                table.add_row(
                    entity,
                    self.variation_text(entity),
                    self.outcome(entity, refusals, realized),
                )

        self.console.print(table)

        if resolution:
            system, user = resolution.render("‹case›")
            self.console.print("system", style="bold")
            self.console.print(Text(_clipped(system) or "(none)"))
            self.console.print("user", style="bold")
            self.console.print(Text(user))

    def do_reasoning(self) -> None:
        variations = sorted(
            (
                ReasoningBranchSpec.model_validate(model)
                for model in select_visible_branch_models("reasoning", self.identity)
            ),
            key=lambda v: (
                EFFORTS.index(v.target.effort),
                v.target.budget or 0,
                v.name,
            ),
        )
        stacks = self.stacks()
        slices = self.slices if self.configuration else None

        caption = (
            f"sampling as '{self.name_of('sampling', slices.sampling)}' pulls it in"
            if slices
            else "the cell has no configuration: no sampling is pulled in"
        )
        # A column per stack, but stacks every variation resolves alike on
        # share one: they differ in nothing this table shows.
        columns: dict[tuple[str, ...], tuple[list[str], list[Text]]] = {}

        for stack in stacks:
            cells = [
                _effort(
                    *realize(
                        variation.target,
                        slices.sampling if slices else None,
                        self.facts_of(stack),
                        stack.target.serving,
                    )
                )
                for variation in variations
            ]
            names, _ = columns.setdefault(
                tuple(cell.plain for cell in cells), ([], cells)
            )
            current = self.stack is not None and self.stack.name == stack.name
            names.append(f"▸ {stack.name}" if current else stack.name)

        table = Table(header_style="bold", show_lines=True, caption=caption)
        table.add_column("reasoning")

        for names, _ in columns.values():
            table.add_column("\n".join(names), overflow="fold")

        for i, variation in enumerate(variations):
            current = slices is not None and _same(slices.reasoning, variation.target)
            table.add_row(
                f"▸ {variation.name}" if current else variation.name,
                *(cells[i] for _, cells in columns.values()),
            )

        self.console.print(table)

    def do_run(self, name: str, seed: str | None = None) -> None:
        if seed is not None and not seed.isdigit():
            self.error(f"a seed is a whole number, not '{seed}'")
            return

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

        tools = self.tools()
        implementations = {
            name: branch.details.implementation.entry_point
            for name, branch in tools.items()
            if branch.details.implementation is not None
        }
        missing = [t.name for t in resolution.tools if t.name not in implementations]

        if missing:
            self.error(f"nothing to run for {', '.join(missing)}: no implementation")
            return

        seeded = f" (seed {seed})" if seed is not None else ""
        header = f"{self.label} × {self.stack.name} × {case.name}{seeded}"
        self.console.print(f"trial: {header}", style="bold")

        trial = Trial(
            resolution,
            case.target.payload,
            api_key=api_key,
            transport=self.transport,
            seed=int(seed) if seed is not None else None,
            implementations=implementations,
        )

        # an answer that doesn't come, or doesn't parse, is one that doesn't
        # hold, where one is asked for
        unheld = False if resolution.coercion is not None else None
        started = timezone.now()

        try:
            streamed = asyncio.run(self.stream(trial))
        except KeyboardInterrupt:
            self.console.print("\n(stopped)", style=LABEL)
            outcome = Outcome(RunStatus.ERRORED, error="stopped")
        except UnexpectedModelBehavior as e:
            unparsed = f"the answer doesn't parse: {cause_of(e)}"
            self.error(f"invalid: {unparsed}")
            outcome = Outcome(RunStatus.COMPLETED, valid=unheld, error=unparsed)
        except UsageLimitExceeded:
            stopped = f"stopped: still calling tools after {TOOL_ROUNDS} rounds"
            self.error(f"\n{stopped}")
            outcome = Outcome(RunStatus.COMPLETED, valid=unheld, error=stopped)
        except Exception as e:  # noqa: BLE001
            # the model or its server failed mid-run: say so and carry on
            self.error(f"\n{type(e).__name__}: {e}")
            outcome = Outcome(RunStatus.ERRORED, error=f"{type(e).__name__}: {e}")
        else:
            valid = self.judge(resolution, streamed)
            outcome = Outcome(RunStatus.COMPLETED, output=streamed.answer, valid=valid)

        finished = timezone.now()

        try:
            run = record(
                self.identity,
                ConfigurationTrailSchema.model_validate(
                    self.slices, from_attributes=True
                ),
                Branches(
                    stack=self.stack.id,
                    model=self.model_of(self.stack)[1],
                    tools=[branch.id for branch in tools.values()],
                ),
                case.target_id,
                trial,
                outcome,
                started,
                finished,
                description=header,
            )
        except Exception as e:  # noqa: BLE001
            self.error(f"not recorded: {type(e).__name__}: {e}")
            return

        self.console.print(
            f"recorded as run {run.trial.runs.count()} of trial "
            + str(run.trial.uuid)[:8],
            style=LABEL,
        )

    def do_save(self, name: str) -> None:
        if not self.configuration:
            self.error("the cell has no configuration to save: use CONFIGURATION")
            return

        entity = entity_of("configuration")
        # the cell's configuration as content, what is set in it included
        schema = ConfigurationTrailSchema.model_validate(
            self.slices, from_attributes=True
        )
        had = entity.branch_model.objects.filter(
            owner__name=self.identity, name=name
        ).exists()

        with transaction.atomic():
            trail = dump_trail(ConfigurationTrailModel, schema)
            # what it reaches becomes the identity's too, as the archive has
            # it: a tool keeps what it runs
            copied = commit_copies(trail, self.identity, settings.ARCHIVE_IDENTITY_NAME)
            changed = commit(
                trail,
                entity.branch_details.model_validate(
                    {
                        "name": name,
                        "owner": self.identity,
                        "tags": self.configuration.tags,
                    }
                ),
            )

        what = "a new version" if had and changed else "unchanged" if had else "created"
        self.console.print(
            f"saved as {name}: {what} {short_fingerprint(trail.fingerprint)}"
        )

        if copied:
            self.console.print(Text(f"yours now too: {', '.join(copied)}", style=LABEL))

        # what the identity calls things, and can complete, may have changed
        self._names.clear()
        self._completions = None
        self.put_configuration(get_branch_model("configuration", self.identity, name))
        self.say_cell()

    def do_runs(self, count: str = "20") -> None:
        if not count.isdigit():
            self.error(f"a count is a whole number, not '{count}'")
            return

        runs = list(
            RunModel.objects.filter(owner__name=self.identity)
            .select_related("trial", "session")
            .order_by("-timestamp", "-pk")[: int(count)]
        )

        if not runs:
            self.console.print(f"{self.identity} has no runs", style=LABEL)
            return

        table = Table(box=None, header_style="bold")

        for column in ("run", "when", "trial", "what ran", "outcome"):
            table.add_column(column)

        for run in runs:
            table.add_row(
                _short(run.uuid),
                _when(run.timestamp),
                _short(run.trial.uuid),
                run.session.description if run.session else "—",
                _outcome(run),
            )

        self.console.print(table)

    def do_replay(self, prefix: str | None = None) -> None:
        runs = RunModel.objects.filter(owner__name=self.identity).select_related(
            "trial__configuration__output", "session", "client"
        )

        if prefix is not None:
            runs = runs.filter(uuid__startswith=prefix)

        found = list(runs.order_by("-timestamp", "-pk")[:2])

        if not found:
            which = f"no run '{prefix}'" if prefix else "no runs"
            self.error(f"{self.identity} has {which}")
            return

        if prefix is not None and len(found) > 1:
            self.error(f"more than one run starts with '{prefix}'")
            return

        run = found[0]
        what = run.session.description if run.session else "—"
        self.console.print(
            f"run {_short(run.uuid)} of trial {_short(run.trial.uuid)}: {what}",
            style="bold",
        )
        self.console.print(
            f"{_when(run.timestamp)}, {run.status}, {_client(run)}", style=LABEL
        )

        stored = list(run.session.messages.all()) if run.session else []
        messages = ModelMessagesTypeAdapter.validate_python(
            [message.payload for message in stored if message.kind != MessageKind.ERROR]
        )
        answered = run.output is not None
        show_messages(self.console, messages, answered)

        for message in stored:
            if message.kind == MessageKind.ERROR:
                self.error(str(message.payload["error"]))

        if answered:
            output = cast(
                OutputTrailSpec,
                load_trail(
                    "output",
                    run.trial.configuration.output.fingerprint,
                    OutputTrailSpec,
                ),
            )

            if run.valid is not None and output.schema is not None:
                show_validity(self.console, invalid(output.schema, run.output))

            show_views(self.console, output, run.output)

    # -------------------------------------------------------------- helpers

    def tools(self) -> dict[str, ToolBranchSpec]:
        """The branch of each of the cell's tools, which says what it runs."""
        toolset = self.variation("toolset") if self.configuration else None
        found: dict[str, ToolBranchSpec] = {}

        for tool in toolset.tools if toolset else []:
            try:
                model = get_visible_branch_model("tool", self.identity, trail=tool.id)
            except (BranchNotFoundError, AmbiguousBranchError):
                continue

            found[tool.name] = ToolBranchSpec.model_validate(model)

        return found

    def put_configuration(self, model: Any) -> None:
        # a configuration goes in as it is: what was set was set in another
        self.configuration = ConfigurationBranchSpec.model_validate(model)
        self.variations = {}

    def stacks(self) -> list[StackBranchSpec]:
        return [
            StackBranchSpec.model_validate(model)
            for model in select_visible_branch_models("stack", self.identity)
        ]

    def facts_of(self, stack: StackBranchSpec) -> ModelFacts:
        """The facts of the stack's model, as the identity's branch has them."""
        return self.model_of(stack)[0]

    def model_of(self, stack: StackBranchSpec) -> tuple[ModelFacts, int | None]:
        """The facts of the stack's model, and the branch row they are read from."""
        model_id = stack.target.model.id

        if model_id not in self._models:
            try:
                model = get_visible_branch_model("model", self.identity, trail=model_id)
                facts = ModelBranchSpec.model_validate(model).details.facts
                self._models[model_id] = (facts, model.pk)
            except (BranchNotFoundError, AmbiguousBranchError):
                # none to read: resolution refuses for want of them
                self._models[model_id] = (ModelFacts(), None)

        return self._models[model_id]

    def resolve(self) -> Resolution:
        assert self.configuration and self.stack

        return resolve(
            self.slices,
            self.stack.details,
            self.facts_of(self.stack),
            self.stack.target.serving,
        )

    async def stream(self, trial: Trial) -> Streamed:
        async with trial.stream() as events:
            return await show_events(self.console, events)

    def judge(self, resolution: Resolution, streamed: Streamed) -> bool | None:
        """
        Whether the model reasoned as it was asked to, whether its answer
        holds to its schema, and what the output's views read from it.
        Answer with whether it holds, where there is a schema to hold to.
        """
        # The facts are claims: a trial is what shows whether the model
        # honours them (new-datamodel.md §2).
        intent = resolution.reasoning.intent

        if intent != "off" and not streamed.thought:
            self.console.print(
                Text(
                    f"no thinking came back, though reasoning resolved to '{intent}'",
                    style=LATER,
                )
            )
        elif intent == "off" and streamed.thought:
            self.console.print(
                Text(
                    "thinking came back, though reasoning resolved to 'off'",
                    style=LATER,
                )
            )

        answer = streamed.answer
        valid: bool | None = None

        if resolution.coercion is not None:
            problem = invalid(resolution.coercion.schema, answer)
            valid = problem is None
            show_validity(self.console, problem)

        show_views(self.console, resolution.output, answer)

        return valid

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

    def variation_text(self, entity: EntityName) -> Text:
        assert self.configuration

        own = self.name_of(entity, getattr(self.configuration.target, entity))

        if entity not in self.variations:
            return Text(own)

        text = Text(self.set_name(entity), style="bold")
        text.append(f" (set; {self.configuration.name} has {own})", style=LABEL)
        return text

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
        configuration = self.label or "?"
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
type Parts = tuple[
    Reasoning | None, Sampling | None, Coercion | None, list[Tool], dict[str, str]
]


def _realized(entity: str, slices: Slices, parts: Parts) -> str:
    reasoning, sampling, coercion, tools, slots = parts
    free_text = slices.output.schema is None
    views = ", ".join(slices.output.views) or "none"

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
        case "output":
            return f"{'free text' if free_text else 'a schema'}; views: {views}"
        case "coercion" if free_text:
            return "nothing to coerce in free text"
        case "coercion" if coercion:
            return _coerced(coercion, SCHEMA_PROMPT in slots)
        case "instruction":
            return f"filled: {', '.join(slots) or 'no slots'}"
        case "toolset" if tools:
            return f"offered: {', '.join(tool.name for tool in tools)}"
        case _:
            return ""


def _coerced(coercion: Coercion, shown: bool) -> str:
    """How the answer is held to its schema, and how the model reads it."""
    match coercion.mode:
        case "native":
            held = "response_format: guided decoding holds the answer to the schema"
        case "tool":
            held = f"a {FINAL_RESULT} tool holds the answer to the schema"
        case "prompted":
            held = "nothing holds the answer to the schema"

    reads = [
        *(["as the tool's parameters"] if coercion.mode == "tool" else []),
        *(["through schema_prompt"] if shown else []),
    ]
    how = (
        f"the model reads it {' and '.join(reads)}"
        if reads
        else "the model doesn't read it"
    )
    auto = f"auto → {coercion.mode}: " if coercion.requested == "auto" else ""
    note = f"\n{coercion.note}" if coercion.note else ""

    return f"{auto}{held}; {how}{note}"


def _clipped(text: str, lines: int = 30) -> str:
    kept = text.splitlines()

    if len(kept) <= lines:
        return text

    return "\n".join(kept[:lines]) + f"\n… {len(kept) - lines} more lines"


def _effort(
    reasoning: Reasoning | None,
    sampling: Sampling | None,
    refusals: list[SliceRefusal],
) -> Text:
    """A reasoning variation on a stack, as the table shows it."""
    if refusals:
        return Text(
            "\n".join(f"refused: {refusal.reason}" for refusal in refusals),
            style=REFUSED,
        )

    assert reasoning

    text = Text()

    if reasoning.effort != reasoning.intent:
        # the model's default, or a collapse: the intent it ends at
        text.append(f"→ {reasoning.intent}\n")

    text.append(_writes(reasoning.writes) or "nothing")

    if sampling:
        text.append(f"\n{_writes(sampling.writes) or 'nothing'}", style=LABEL)

    return text


def _same(trail: Any, other: Any) -> bool:
    return trail.fingerprint == other.fingerprint


def _writes(writes: dict[str, JsonValue], prefix: str = "") -> str:
    """Request fields as `path=value`, a nested field by its dotted path."""
    fields: list[str] = []

    for key, value in writes.items():
        if isinstance(value, dict):
            fields.append(_writes(value, f"{prefix}{key}."))
        else:
            fields.append(f"{prefix}{key}={json.dumps(value)}")

    return " ".join(field for field in fields if field)


def _short(value: Any) -> str:
    """An id as the repl shows it: the first digits of a uuid."""
    return str(value)[:8]


def _when(moment: datetime) -> str:
    return timezone.localtime(moment).strftime("%Y-%m-%d %H:%M")


def _client(run: RunModel) -> str:
    """The client a run ran on: its build, or the revision of a dev shell."""
    if run.client is None:
        return "on no client it recorded"

    if run.client.build is not None:
        return f"on {run.client.build}"

    rev = run.client_rev or ""
    dirty = "-dirty" if rev.endswith("-dirty") else ""

    return f"from a dev shell at {rev[:12]}{dirty}" if rev else "from a dev shell"


def _outcome(run: RunModel) -> Text:
    """What came of a run, as the list of runs says it."""
    if run.status == RunStatus.ERRORED:
        return Text(f"errored: {_clipped_line(run.error or '')}", style=REFUSED)

    if run.error is not None:
        # it came to no answer that holds
        return Text(_clipped_line(run.error), style=REFUSED)

    match run.valid:
        case True:
            return Text("valid", style=VALID)
        case False:
            return Text("invalid", style=REFUSED)
        case None:
            return Text(run.status)


def _clipped_line(text: str, width: int = 60) -> str:
    line = text.splitlines()[0] if text else ""
    return line if len(line) <= width else line[: width - 1] + "…"


class Transcript:
    """A run written out as it comes: each part on a line of its own, labelled."""

    def __init__(self, console: Console):
        self.console: Console = console
        self.at_start: bool = True
        # just after a label: what follows it starts on its line
        self.labelled: bool = False

    def write(self, text: str, style: str = "") -> None:
        if self.labelled:
            text = text.lstrip()

        if text:
            self.console.out(text, style=style or None, end="", highlight=False)
            self.at_start = text.endswith("\n")
            self.labelled = False

    def begin(self, label: str | None) -> None:
        if not self.at_start:
            self.console.out("")
            self.at_start = True

        self.labelled = False

        if label:
            self.console.out(f"[{label}] ", style=LABEL, end="", highlight=False)
            self.at_start = False
            self.labelled = True

    def usage(self, input_tokens: int, output_tokens: int, requests: int) -> None:
        self.begin(None)
        rounds = f", {requests} requests" if requests > 1 else ""
        self.console.out(
            f"({input_tokens} in, {output_tokens} out{rounds})",
            style=LABEL,
            highlight=False,
        )


def _thinking(origin: str | None) -> str:
    # pydantic-ai marks thinking it found between <think> tags in the
    # content: no reasoning parser took it out
    return "thinking in content" if origin == "content" else "thinking"


async def show_events(console: Console, events: AgentRunEvents[Any]) -> Streamed:
    """
    Write out a trial's events as they come: its thinking, then its answer,
    as text or as the call that gives it. Answer with the answer, and
    whether any thinking came back.
    """
    out = Transcript(console)
    answer: Any = None
    thought = False

    async for event in events:
        match event:
            case PartStartEvent(part=ThinkingPart(content=text, id=origin)):
                out.begin(_thinking(origin))
                out.write(text, THINKING)
                thought = True
            case PartDeltaEvent(delta=ThinkingPartDelta(content_delta=text)) if text:
                out.write(text, THINKING)
                thought = True
            case PartStartEvent(part=TextPart(content=text)):
                out.begin(None)
                out.write(text)
            case PartDeltaEvent(delta=TextPartDelta(content_delta=text)):
                out.write(text)
            case PartStartEvent(part=ToolCallPart(tool_name=name, args=args)):
                out.begin(name)
                out.write(_arguments(args))
            case PartDeltaEvent(delta=ToolCallPartDelta(args_delta=args)) if args:
                out.write(_arguments(args))
            case FunctionToolResultEvent(part=ToolReturnPart(content=content)):
                out.begin("result")
                out.write(_arguments(content))
                out.begin(None)
            case PartEndEvent():
                out.begin(None)
            case AgentRunResultEvent(result=result):
                answer = result.output
                usage = result.usage
                out.usage(usage.input_tokens, usage.output_tokens, usage.requests)
            case _:
                pass

    return Streamed(answer, thought)


def show_messages(
    console: Console, messages: list[ModelMessage], answered: bool
) -> None:
    """
    Write out a recorded run's messages as its events came when it ran, and
    what it used, if it came to an answer.
    """
    out = Transcript(console)
    responses = [message for message in messages if isinstance(message, ModelResponse)]

    for message in messages:
        match message:
            case ModelResponse(parts=parts):
                for part in parts:
                    match part:
                        case ThinkingPart(content=text, id=origin):
                            out.begin(_thinking(origin))
                            out.write(text, THINKING)
                        case TextPart(content=text):
                            out.begin(None)
                            out.write(text)
                        case ToolCallPart(tool_name=name, args=args):
                            out.begin(name)
                            out.write(_arguments(args))
                        case _:
                            pass

                    out.begin(None)
            case ModelRequest(parts=parts):
                for part in parts:
                    # what the answer's own tool returns, the model never reads
                    if (
                        isinstance(part, ToolReturnPart)
                        and part.tool_name != FINAL_RESULT
                    ):
                        out.begin("result")
                        out.write(_arguments(part.content))
                        out.begin(None)

    if answered:
        out.usage(
            sum(response.usage.input_tokens for response in responses),
            sum(response.usage.output_tokens for response in responses),
            len(responses),
        )


def show_validity(console: Console, problem: str | None) -> None:
    if problem is None:
        console.print("valid", style=VALID)
    else:
        console.print(Text(f"invalid: {problem}", style=REFUSED))


def show_views(console: Console, output: OutputTrailBase, answer: Any) -> None:
    """What each of the output's views reads from the answer."""
    for view in output.views:
        items = output.view(view, answer)
        console.print(view, style="bold")

        for i, item in enumerate(items, 1):
            text = item if isinstance(item, str) else json.dumps(item)
            console.print(Text(f"  {i}. {text}"))

        if not items:
            console.print("  nothing", style=LABEL)


def _arguments(args: Any) -> str:
    """A tool call's arguments, or a piece of them, as they were sent."""
    match args:
        case str():
            return args
        case None:
            return ""
        case dict():
            return json.dumps(args)
        case _:
            return str(args)


def complete(names: dict[str, list[str]], line: str) -> list[str]:
    """What the last word of `line` can be: a command, then the names it takes."""
    verb, *words = line.split(" ")

    if not words:
        return [command for command in COMMANDS if command.startswith(verb)]

    params = COMMANDS.get(verb, ((), ""))[0]
    position = len(words) - 1

    if position >= len(params):
        return []

    match params[position]:
        case "SLICE":
            candidates = list(SLICES)
        case "VARIATION":
            # a variation of the slice named before it
            entity = words[position - 1]
            candidates = names.get(entity, []) + ([NONE] if entity in OPTIONAL else [])
        case param:
            candidates = names.get(param.lower(), [])

    return [name for name in candidates if name.startswith(words[-1])]


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

    def completer(_word: str, state: int) -> str | None:
        line = readline.get_line_buffer()[: readline.get_endidx()]
        matches = complete(shell.completions(), line)
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

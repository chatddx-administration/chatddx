# pyright: basic
from collections.abc import Iterable
from typing import Any

from rich.console import Console
from rich.text import Text

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.core.repl.cell import SLICES, Cell
from chatddx.core.repl.render import LATER, REFUSED
from chatddx.history.models import RunModel
from chatddx.repo.entities.model.pydantic import ModelBranchOut, ModelFacts
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.entities.tool.pydantic import ToolBranchOut
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.names import short_fingerprint
from chatddx.repo.store.branch import (
    AmbiguousBranchError,
    BranchNotFoundError,
    get_shared_branch_model,
    get_visible_branch_model,
    select_visible_branch_models,
)
from chatddx.runtime.resolution import Resolution, SliceRefusal, resolve
from chatddx.scoring.score import Scoring

SHARED_BY: dict[str, str] = {"configuration": settings.ARCHIVE_IDENTITY_NAME}


class NotFound(Exception):
    pass


class Repl:
    """
    What the repl holds: the identity it runs as, the console it writes to,
    the transport trials go through in place of the stack's endpoint, where
    one is given, and a cell.

    Names are looked up as the identity sees them: its own branches first,
    then those shared with it. A configuration is looked up among its own
    and the archive's alone (SHARED_BY), as those are what it runs; one
    another user shares is called by its owner, OWNER/NAME, and runs once
    it is saved as the identity's own.
    """

    def __init__(self, identity_name: str, console: Console, transport: Any = None):
        self.identity: str = identity_name
        self.console: Console = console
        self.transport: Any = transport
        self.cell: Cell = Cell()

        self._names: dict[tuple[EntityName, int], str] = {}
        self._models: dict[int, tuple[ModelFacts, int | None]] = {}
        self._completions: dict[str, list[str]] | None = None

    @property
    def prompt(self) -> str:
        cell = self.cell
        stack = f"×{cell.stack.name}" if cell.stack else ""
        held = f" {cell.label}{stack}" if cell.configuration or cell.stack else ""
        return f"{self.identity}{held}> "

    def completions(self) -> dict[str, list[str]]:
        """
        The names a command's words complete from: those of the registry,
        looked up once, and the runs as they are now, the latest first.
        """
        if self._completions is None:
            self._completions = {
                entity: self.names(entity)
                for entity in ("configuration", "stack", "case", *SLICES)
            }

        latest = RunModel.objects.filter(owner__name=self.identity).order_by(
            "-timestamp", "-pk"
        )
        outstanding = Scoring(self.identity).outstanding_runs()

        return self._completions | {
            "replay:run": [
                str(uuid)[:8] for uuid in latest.values_list("uuid", flat=True)[:20]
            ],
            "score:run": [str(run.uuid)[:8] for run in reversed(outstanding)],
        }

    def forget(self) -> None:
        """Look names up anew: what the identity calls things has changed."""
        self._names.clear()
        self._completions = None

    def names(self, entity: EntityName) -> list[str]:
        models = select_visible_branch_models(
            entity, self.identity, SHARED_BY.get(entity)
        )
        return sorted({model.name for model in models})

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

    def run_named(self, prefix: str | None) -> RunModel:
        """The identity's run whose id starts with `prefix`, or its latest."""
        runs = RunModel.objects.filter(owner__name=self.identity).select_related(
            "trial__configuration__output", "session", "client"
        )

        if prefix is not None:
            runs = runs.filter(uuid__startswith=prefix)

        found = list(runs.order_by("-timestamp", "-pk")[:2])

        if not found:
            which = f"no run '{prefix}'" if prefix else "no runs"
            raise NotFound(f"{self.identity} has {which}")

        if prefix is not None and len(found) > 1:
            raise NotFound(f"more than one run starts with '{prefix}'")

        return found[0]

    def configuration_named(self, name: str) -> BranchModel:
        """The configuration the identity means by NAME, or by OWNER/NAME."""
        owner, slash, branch = name.partition("/")

        if not slash:
            return get_visible_branch_model(
                "configuration",
                self.identity,
                name,
                shared_by=SHARED_BY["configuration"],
            )

        return get_shared_branch_model("configuration", self.identity, owner, branch)

    def stacks(self) -> list[StackBranchOut]:
        return [
            StackBranchOut.model_validate(model)
            for model in select_visible_branch_models("stack", self.identity)
        ]

    def facts_of(self, stack: StackBranchOut) -> ModelFacts:
        """The facts of the stack's model, as the identity's branch has them."""
        return self.model_of(stack)[0]

    def model_of(self, stack: StackBranchOut) -> tuple[ModelFacts, int | None]:
        """
        The facts of the stack's model, and the branch row they are read
        from: none where the identity has no branch of it, and resolution
        refuses for want of them.
        """
        model_id = stack.target.model.id

        if model_id not in self._models:
            try:
                model = get_visible_branch_model("model", self.identity, trail=model_id)
                facts = ModelBranchOut.model_validate(model).details.facts
                self._models[model_id] = (facts, model.pk)
            except (BranchNotFoundError, AmbiguousBranchError):
                self._models[model_id] = (ModelFacts(), None)

        return self._models[model_id]

    def tools(self) -> dict[str, ToolBranchOut]:
        """The branch of each of the cell's tools, which says what it runs."""
        toolset = self.cell.variation("toolset") if self.cell.configuration else None
        found: dict[str, ToolBranchOut] = {}

        for tool in toolset.tools if toolset else []:
            try:
                model = get_visible_branch_model("tool", self.identity, trail=tool.id)
            except (BranchNotFoundError, AmbiguousBranchError):
                continue

            found[tool.name] = ToolBranchOut.model_validate(model)

        return found

    def resolve(self) -> Resolution:
        cell = self.cell
        assert cell.configuration and cell.stack

        return resolve(
            cell.slices,
            cell.stack.details,
            self.facts_of(cell.stack),
            cell.stack.target.serving,
        )

    def secret(self, name: str | None) -> str | None:
        if name is None:
            return None

        identity = IdentityModel.objects.get(name=self.identity)
        secret = identity.secrets.get(name)

        return secret if isinstance(secret, str) else None

    def say_cell(self) -> None:
        configuration = self.cell.label or "?"
        stack = self.cell.stack.name if self.cell.stack else "?"
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

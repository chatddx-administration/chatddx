import secrets
from collections.abc import Iterable
from typing import Any

from django.db.models import prefetch_related_objects
from rich.console import Console
from rich.text import Text

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.history.models import RunModel
from chatddx.repl.cell import Cell
from chatddx.repl.render import LATER, REFUSED
from chatddx.repo.entities.llm.pydantic import LLMBranchOut, LLMFacts
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.entities.tool.pydantic import ToolBranchOut
from chatddx.repo.entity_names import ENTITY_NAMES, EntityName
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

SEEDS = 100_000

DRAWN: Any = object()


def drawn_seed() -> int:
    return secrets.randbelow(SEEDS)


class NotFound(Exception):
    pass


class Repl:
    def __init__(
        self,
        identity_name: str,
        console: Console,
        transport: Any = None,
        seed: int | None = DRAWN,
    ):
        self.identity: str = identity_name
        self.console: Console = console
        self.transport: Any = transport
        self.cell: Cell = Cell()
        self.seed: int | None = drawn_seed() if seed is DRAWN else seed

        self._names: dict[tuple[EntityName, int], str] = {}
        self._llms: dict[int, tuple[LLMFacts, int | None]] = {}
        self._completions: dict[str, list[str]] | None = None

    @property
    def prompt(self) -> str:
        cell = self.cell
        stack = f"×{cell.stack.name}" if cell.stack else ""
        held = f" {cell.label}{stack}" if cell.configuration or cell.stack else ""
        seed = f"#{self.seed}" if self.seed is not None else "#none"
        return f"{self.identity}{held} {seed}> "

    def completions(self) -> dict[str, list[str]]:
        if self._completions is None:
            self._completions = {
                entity: self.names(entity) for entity in ENTITY_NAMES
            } | {"batch:tag": self.tags("case"), "seed:seed": ["none"]}

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
        self._names.clear()
        self._completions = None

    def names(self, entity: EntityName) -> list[str]:
        models = select_visible_branch_models(
            entity, self.identity, SHARED_BY.get(entity)
        )
        return sorted({model.name for model in models})

    def tags(self, entity: EntityName) -> list[str]:
        """The tags of the branches of `entity` the identity can use."""
        return sorted(
            {tag.name for model in self.usable(entity) for tag in model.tags.all()}
        )

    def tagged(self, entity: EntityName, tags: Iterable[str]) -> list[BranchModel]:
        wanted = set(tags)

        return [
            model
            for model in self.usable(entity)
            if wanted & {tag.name for tag in model.tags.all()}
        ]

    def usable(self, entity: EntityName) -> list[BranchModel]:
        models = select_visible_branch_models(
            entity, self.identity, SHARED_BY.get(entity)
        )
        prefetch_related_objects(models, "tags")

        return models

    def name_of(self, entity: EntityName, trail: Any) -> str:
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
        runs = RunModel.objects.filter(owner__name=self.identity).select_related(
            "trial__configuration__output", "conversation", "client"
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

    def facts_of(self, stack: StackBranchOut) -> LLMFacts:
        """The facts of the stack's LLM, as the identity's branch has them."""
        return self.llm_of(stack)[0]

    def llm_of(self, stack: StackBranchOut) -> tuple[LLMFacts, int | None]:
        llm_id = stack.trail.llm.id

        if llm_id not in self._llms:
            try:
                llm = get_visible_branch_model("llm", self.identity, trail=llm_id)
                facts = LLMBranchOut.model_validate(llm).details.facts
                self._llms[llm_id] = (facts, llm.pk)
            except (BranchNotFoundError, AmbiguousBranchError):
                self._llms[llm_id] = (LLMFacts(), None)

        return self._llms[llm_id]

    def tools(self) -> dict[str, ToolBranchOut]:
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
            cell.stack.trail.serving,
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

"""What the repl and the API share: a cell, and the registry as an identity sees it."""

import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from django.db import transaction
from django.db.models import Q, prefetch_related_objects
from pydantic_ai import UnexpectedModelBehavior, UsageLimitExceeded

from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.history.models import ConversationContext, RunModel, RunStatus
from chatddx.history.record import Branches, Outcome, record
from chatddx.repl.cell import SLICES, Cell
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.case.pydantic import pattern_of
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailIn
from chatddx.repo.entities.llm.pydantic import LLMBranchOut, LLMFacts
from chatddx.repo.entities.reasoning.pydantic import Intent
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.entities.tool.pydantic import ToolBranchOut
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.families.pydantic import BranchOut
from chatddx.repo.names import short_fingerprint
from chatddx.repo.store.branch import (
    AmbiguousBranchError,
    BranchNotFoundError,
    commit,
    commit_copies,
    get_branch_model,
    get_shared_branch_model,
    get_visible_branch_model,
    select_visible_branch_models,
)
from chatddx.repo.store.trail import dump_trail
from chatddx.runtime.resolution import Resolution, Sampling, resolve
from chatddx.runtime.run import TOOL_ROUNDS, Run, Runaway, cause_of, invalid
from chatddx.scoring.score import Scoring, VisibleScorer
from chatddx.scoring.scorers.patterns import Pattern

SHARED_BY: dict[str, str] = {"configuration": settings.ARCHIVE_IDENTITY_NAME}

HELD_AT: dict[str, str] = {
    "case": "trial__case",
    "configuration": "trial__configuration",
    "stack": "trial__stack",
    "client": "client",
    "machine": "trial__stack__machine",
    "llm": "trial__stack__llm",
    "serving": "trial__stack__serving",
    **{entity: f"trial__configuration__{entity}" for entity in SLICES},
}

SEEDS = 100_000

MAX_SEED = 2**63 - 1

STOPPED = Outcome(RunStatus.ERRORED, error="stopped")


def drawn_seed() -> int:
    return secrets.randbelow(SEEDS)


class NotFound(Exception):
    pass


class Ambiguous(NotFound):
    pass


@dataclass(frozen=True)
class Ready:
    resolution: Resolution
    api_key: str | None
    tools: dict[str, ToolBranchOut]


@dataclass(frozen=True)
class HeldTo:
    scorer: VisibleScorer
    offered: bool
    cases: int
    missing: list[str]
    unread: list[str]

    @property
    def have(self) -> int:
        return self.cases - len(self.missing) - len(self.unread)


@dataclass(frozen=True)
class Saved:
    name: str
    fingerprint: str
    what: Literal["created", "a new version", "unchanged"]
    copied: list[str]


class Bench:
    def __init__(self, identity_name: str, transport: Any = None):
        self.identity: str = identity_name
        self.transport: Any = transport
        self.cell: Cell = Cell()

        self._names: dict[tuple[EntityName, int], str] = {}
        self._llms: dict[int, tuple[LLMFacts, int | None]] = {}

    def forget(self) -> None:
        self._names.clear()

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

    def cases(self, tags: Iterable[str] = ()) -> list[BranchModel]:
        """The cases with any of `tags`, or all, a vignette once, by name."""
        tags = tuple(tags)
        distinct: dict[int, BranchModel] = {}

        for case in self.tagged("case", tags) if tags else self.usable("case"):
            _ = distinct.setdefault(case.trail_id, case)

        return list(distinct.values())

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
            raise Ambiguous(f"more than one run starts with '{prefix}'")

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

    def called(self, name: str) -> str:
        """What the cell calls a configuration: what it was named, one's own bare."""
        return name.removeprefix(f"{self.identity}/")

    def variation_named(self, entity: EntityName, name: str) -> BranchOut[Any, Any]:
        model = get_visible_branch_model(entity, self.identity, name)
        return entity_of(entity).branch_out.model_validate(model)

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

    def held_to(self, cases: list[BranchModel]) -> list[HeldTo]:
        """Each scorer, and which of `cases` it can hold the cell to."""
        views = self.cell.slices.output.views
        found: list[HeldTo] = []

        for scorer in Scoring(self.identity).scorers:
            offered = scorer.view in views
            missing: list[str] = []
            unread: list[str] = []

            for case in cases if offered and scorer.target_kind else []:
                target = case.details.get("targets", {}).get(scorer.target_kind)
                pattern = pattern_of(target)

                if target is False:
                    continue

                if pattern is None:
                    missing.append(case.name)
                elif unread_pattern(pattern) is not None:
                    unread.append(case.name)

            found.append(HeldTo(scorer, offered, len(cases), missing, unread))

        return found

    def made(self, ready: Ready, vignette: str, seed: int | None) -> Run:
        return Run(
            ready.resolution,
            vignette,
            api_key=ready.api_key,
            transport=self.transport,
            seed=seed,
            implementations={
                tool: branch.details.implementation.function
                for tool, branch in ready.tools.items()
                if branch.details.implementation is not None
            },
        )

    def described(self, case: str, seed: int | None) -> str:
        cell = self.cell
        assert cell.stack
        seeded = f" (seed {seed})" if seed is not None else ""

        return f"{cell.label} × {cell.stack.name} × {case}{seeded}"

    def recorded(
        self,
        ready: Ready,
        case: int,
        run: Run,
        outcome: Outcome,
        started: datetime,
        finished: datetime,
        description: str,
        context: ConversationContext = ConversationContext.REPL,
    ) -> RunModel:
        cell = self.cell
        assert cell.stack

        return record(
            self.identity,
            ConfigurationTrailIn.model_validate(cell.slices, from_attributes=True),
            Branches(
                stack=cell.stack.id,
                llm=self.llm_of(cell.stack)[1],
                tools={
                    ready.tools[tool].id: ran.blob
                    for tool, ran in run.implementations.items()
                },
            ),
            case,
            run,
            outcome,
            started,
            finished,
            description=description,
            context=context,
        )

    def runs_with(self, entity: EntityName, trail: int) -> list[RunModel]:
        """The identity's runs with the trail, the latest first."""
        match entity:
            case "os":
                with_it = Q(trial__stack__os=trail) | Q(trial__stack__host_os=trail)
            case "tool":
                with_it = Q(trial__configuration__toolset__tools__contains=[trail])
            case "scorer":
                with_it = Q(scores__scorer=trail, scores__owner__name=self.identity)
            case _:
                with_it = Q(**{HELD_AT[entity]: trail})

        return list(
            RunModel.objects.filter(with_it, owner__name=self.identity)
            .distinct()
            .select_related("trial", "conversation")
            .prefetch_related("scores")
            .order_by("-timestamp", "-pk")
        )

    def save(self, name: str) -> Saved:
        """
        Keep the cell's configuration, what is set in it included, as the
        identity's own. What it reaches becomes the identity's too, as the
        archive has it: a tool keeps what it runs.
        """
        cell = self.cell
        assert cell.configuration

        if "/" in name:
            raise ValueError(
                f"a name can't hold '/', which parts an owner from a name: {name}"
            )

        entity = entity_of("configuration")
        schema = ConfigurationTrailIn.model_validate(cell.slices, from_attributes=True)
        had = entity.branch_model.objects.filter(
            owner__name=self.identity, name=name
        ).exists()

        with transaction.atomic():
            trail = dump_trail(ConfigurationTrailModel, schema)
            copied = commit_copies(trail, self.identity, settings.ARCHIVE_IDENTITY_NAME)
            changed = commit(
                trail,
                entity.branch_details.model_validate(
                    {
                        "name": name,
                        "owner": self.identity,
                        "tags": cell.configuration.tags,
                    }
                ),
            )

        self.forget()
        cell.put(get_branch_model("configuration", self.identity, name), name)

        return Saved(
            name,
            trail.fingerprint,
            "a new version" if had and changed else "unchanged" if had else "created",
            copied,
        )


def greedy(sampling: Sampling) -> bool:
    writes = sampling.writes
    return writes.get("temperature") == 0 or writes.get("top_k") == 1


def failed(error: Exception, resolution: Resolution) -> Outcome:
    unheld = False if resolution.coercion is not None else None

    match error:
        case UnexpectedModelBehavior():
            unparsed = f"the answer doesn't parse: {cause_of(error)}"
            return Outcome(RunStatus.COMPLETED, valid=unheld, error=unparsed)
        case UsageLimitExceeded():
            stopped = f"stopped: still calling tools after {TOOL_ROUNDS} rounds"
            return Outcome(RunStatus.COMPLETED, valid=unheld, error=stopped)
        case Runaway():
            return Outcome(RunStatus.COMPLETED, valid=unheld, error=f"stopped: {error}")
        case _:
            return Outcome(RunStatus.ERRORED, error=f"{type(error).__name__}: {error}")


def holds(resolution: Resolution, answer: Any) -> bool | None:
    if resolution.coercion is None:
        return None

    return invalid(resolution.coercion.schema, answer) is None


def unheeded(intent: Intent, thought: bool) -> str | None:
    if intent != "off" and not thought:
        return f"no thinking came back, though reasoning resolved to '{intent}'"

    if intent == "off" and thought:
        return "thinking came back, though reasoning resolved to 'off'"

    return None


def unread_pattern(pattern: str) -> str | None:
    """Why a target's pattern doesn't parse, if it doesn't."""
    try:
        _ = Pattern(pattern)
    except ValueError as e:
        return str(e)

    return None

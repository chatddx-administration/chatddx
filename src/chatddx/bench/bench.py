import secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from django.db import transaction
from django.db.models import Q, prefetch_related_objects

from chatddx.bench.cell import NONE, SLICES, Cell, Made, labelled, set_in, set_names_of
from chatddx.core import settings
from chatddx.core.models import IdentityModel
from chatddx.history.models import ConversationContext, RunModel, TrialModel
from chatddx.history.record import Outcome, Read, record, trial_of
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.case.pydantic import pattern_of
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.llm.pydantic import LLMBranchOut, LLMFacts
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.entities.tool.pydantic import ToolBranchOut
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchModel
from chatddx.repo.families.pydantic import BranchOut
from chatddx.repo.queries import head_of, reaching
from chatddx.repo.store.branch import (
    AmbiguousBranchError,
    BranchNotFoundError,
    commit,
    commit_copies,
    get_branch_model,
    get_shared_branch_model,
    get_visible_branch_model,
    name_of,
    select_visible_branch_models,
)
from chatddx.repo.store.trail import dump_trail
from chatddx.repo.utils import resolve_trail
from chatddx.runtime.resolution import Resolution, Sampling, resolve
from chatddx.runtime.run import Run
from chatddx.scoring.score import Scoring, VisibleScorer
from chatddx.scoring.scorers.patterns import unread_pattern

SHARED_BY: dict[str, str] = {"configuration": settings.ARCHIVE_IDENTITY_NAME}

SEEDS = 100_000

MAX_SEED = 2**63 - 1


def drawn_seed() -> int:
    return secrets.randbelow(SEEDS)


def greedy(sampling: Sampling) -> bool:
    writes = sampling.writes
    return writes.get("temperature") == 0 or writes.get("top_k") == 1


class NotFound(Exception):
    pass


class Ambiguous(NotFound):
    pass


class NotReady(Exception):
    pass


class Incomplete(NotReady):
    pass


class NotOwn(NotReady):
    pass


class NoSecret(NotReady):
    pass


class Drifted(NotReady):
    pass


@dataclass(frozen=True)
class Ready:
    cell: Cell
    resolution: Resolution
    api_key: str | None
    tools: dict[str, ToolBranchOut]

    @property
    def greedy(self) -> bool:
        return greedy(self.resolution.sampling)


@dataclass(frozen=True)
class Trial:
    ready: Ready
    case: int
    called: str
    vignette: str
    seed: int | None
    planned: TrialModel | None = None

    @classmethod
    def of(
        cls,
        ready: Ready,
        case: Any,
        called: str,
        seed: int | None,
        planned: TrialModel | None = None,
    ) -> "Trial":
        return cls(ready, case.pk, called, case.vignette, seed, planned)

    @classmethod
    def on(cls, ready: Ready, case: BranchModel, seed: int | None) -> "Trial":
        return cls.of(ready, case.trail, case.name, seed)

    @property
    def description(self) -> str:
        return self.ready.cell.described(self.called, self.seed)


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
    cell: Cell


class Bench:
    def __init__(
        self,
        identity_name: str,
        transport: Any = None,
        own: Iterable[EntityName] = (),
    ):
        self.identity: str = identity_name
        self.transport: Any = transport
        self.own: frozenset[EntityName] = frozenset(own)

        self._names: dict[tuple[EntityName, int], str] = {}
        self._llms: dict[int, tuple[LLMFacts, int | None]] = {}

    def forget(self) -> None:
        self._names.clear()

    def visible(self, entity: EntityName) -> list[BranchModel]:
        models = select_visible_branch_models(
            entity, self.identity, SHARED_BY.get(entity)
        )

        if entity in self.own:
            return [model for model in models if model.owner.name == self.identity]

        return models

    def names(self, entity: EntityName) -> list[str]:
        return sorted({model.name for model in self.visible(entity)})

    def tags(self, entity: EntityName) -> list[str]:
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
        models = self.visible(entity)
        prefetch_related_objects(models, "tags")

        return models

    def cases(self, tags: Iterable[str] = ()) -> list[BranchModel]:
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
            self._names[key] = name_of(entity, self.identity, trail)

        return self._names[key]

    def label_of(self, made: Made) -> str:
        configuration = made.configuration_branch
        name = (
            configuration.name
            if configuration is not None
            else self.name_of("configuration", made.trial.configuration)
        )

        return labelled(name, set_names_of(made))

    def described(self, made: Made) -> str:
        trial = made.trial
        seeded = f" (seed {trial.seed})" if trial.seed is not None else ""
        case = self.name_of("case", trial.case)

        return f"{self.label_of(made)} × {made.stack_branch.name} × {case}{seeded}"

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
        return name.removeprefix(f"{self.identity}/")

    def variation_named(self, entity: EntityName, name: str) -> BranchOut[Any, Any]:
        model = get_visible_branch_model(entity, self.identity, name)
        return entity_of(entity).branch_out.model_validate(model)

    def stack_named(self, name: str) -> BranchModel:
        return get_visible_branch_model("stack", self.identity, name)

    def cell_of(
        self,
        configuration: str | None = None,
        stack: str | None = None,
        variations: Mapping[str, str | None] | None = None,
    ) -> Cell:
        cell = Cell()
        held = {entity: name for entity, name in (variations or {}).items() if name}

        if configuration is not None:
            cell = cell.using(
                self.configuration_named(configuration), self.called(configuration)
            )

        if stack is not None:
            cell = cell.on(self.stack_named(stack))

        for entity in SLICES:
            if entity not in held:
                continue

            if not cell.configuration:
                raise ValueError(
                    f"the cell has no configuration to set its {entity} in"
                )

            name = held[entity]
            cell = cell.set(
                entity, None if name == NONE else self.variation_named(entity, name)
            )

        return cell

    def cell_read(self, made: Made) -> Cell:
        configuration = made.configuration_branch
        assert configuration is not None

        configuration.trail = resolve_trail(configuration.trail)
        owner = configuration.owner.name
        name = (
            configuration.name
            if owner in (self.identity, SHARED_BY["configuration"])
            else f"{owner}/{configuration.name}"
        )
        cell = Cell().using(configuration, name)

        for entity, branch in set_in(made).items():
            if branch is None:
                cell = cell.set(entity, None)
                continue

            branch.trail = resolve_trail(branch.trail)
            cell = cell.set(entity, entity_of(entity).branch_out.model_validate(branch))

        stack = made.stack_branch
        head = head_of(StackBranchModel.objects.all(), stack.owner.name, stack.name)

        if head is None or head.trail_id != made.trial.stack_id:
            raise Drifted(f"{stack.name} is another stack than was planned")

        head.trail = resolve_trail(head.trail)
        cell = cell.on(head)

        if cell.fingerprint != made.trial.configuration.fingerprint:
            raise Drifted(f"{cell.label} is another configuration than was planned")

        return cell

    def stacks(self) -> list[StackBranchOut]:
        return [StackBranchOut.model_validate(model) for model in self.visible("stack")]

    def facts_of(self, stack: StackBranchOut) -> LLMFacts:
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

    def tools(self, cell: Cell) -> dict[str, ToolBranchOut]:
        toolset = cell.variation("toolset") if cell.configuration else None
        found: dict[str, ToolBranchOut] = {}

        for tool in toolset.tools if toolset else []:
            try:
                model = get_visible_branch_model("tool", self.identity, trail=tool.id)
            except (BranchNotFoundError, AmbiguousBranchError):
                continue

            found[tool.name] = ToolBranchOut.model_validate(model)

        return found

    def resolve(self, cell: Cell) -> Resolution:
        assert cell.configuration and cell.stack

        return resolve(
            cell.trail,
            cell.stack.details,
            self.facts_of(cell.stack),
            cell.stack.trail.serving,
        )

    def ready(self, cell: Cell) -> Ready:
        if not (cell.configuration and cell.stack):
            raise Incomplete("the cell needs a configuration and a stack")

        owner = cell.configuration.owner.name

        if owner not in (self.identity, SHARED_BY["configuration"]):
            raise NotOwn(f"{cell.name} is {owner}'s: save it as your own first")

        resolution = self.resolve(cell)
        api_key = self.secret(resolution.credential)

        if resolution.credential and api_key is None:
            raise NoSecret(f"{self.identity} has no secret '{resolution.credential}'")

        return Ready(cell, resolution, api_key, self.tools(cell))

    def secret(self, name: str | None) -> str | None:
        if name is None:
            return None

        identity = IdentityModel.objects.get(name=self.identity)
        secret = identity.secrets.get(name)

        return secret if isinstance(secret, str) else None

    def held_to(
        self,
        cell: Cell,
        cases: list[BranchModel],
        scoring: Scoring | None = None,
    ) -> list[HeldTo]:
        views = cell.trail.output.views
        found: list[HeldTo] = []

        for scorer in (scoring or Scoring(self.identity)).scorers:
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

    def made(self, trial: Trial) -> Run:
        ready = trial.ready

        return Run(
            ready.resolution,
            trial.vignette,
            api_key=ready.api_key,
            transport=self.transport,
            seed=trial.seed,
            implementations={
                tool: branch.details.implementation.function
                for tool, branch in ready.tools.items()
                if branch.details.implementation is not None
            },
        )

    def recorded(
        self,
        trial: Trial,
        run: Run,
        outcome: Outcome,
        started: datetime,
        finished: datetime,
        context: ConversationContext = ConversationContext.REPL,
    ) -> RunModel:
        ready = trial.ready
        cell = ready.cell
        assert cell.configuration and cell.stack

        planned = trial.planned or trial_of(
            cell.trail, cell.stack.trail.id, trial.case, trial.seed
        )

        return record(
            self.identity,
            planned,
            Read(
                stack=cell.stack.id,
                llm=self.llm_of(cell.stack)[1],
                configuration=cell.configuration.id,
                variations=cell.set_ids,
                tools={
                    ready.tools[tool].id: ran.blob
                    for tool, ran in run.implementations.items()
                },
            ),
            run,
            outcome,
            started,
            finished,
            description=trial.description,
            context=context,
        )

    def runs_with(self, entity: EntityName, trail: int) -> list[RunModel]:
        trail_model = entity_of(entity).trail_model

        if entity == "scorer":
            with_it = Q(scores__scorer=trail, scores__owner__name=self.identity)
        else:
            with_it = reaching(RunModel, trail_model, [trail]) | reaching(
                TrialModel, trail_model, [trail], through="trial"
            )

        return list(
            RunModel.objects.filter(with_it, owner__name=self.identity)
            .distinct()
            .select_related("trial", "conversation")
            .prefetch_related("scores")
            .order_by("-timestamp", "-pk")
        )

    def save(self, cell: Cell, name: str) -> Saved:
        assert cell.configuration

        if "/" in name:
            raise ValueError(
                f"a name can't hold '/', which parts an owner from a name: {name}"
            )

        entity = entity_of("configuration")
        schema = cell.trail
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

        return Saved(
            name,
            trail.fingerprint,
            "a new version" if had and changed else "unchanged" if had else "created",
            copied,
            cell.using(get_branch_model("configuration", self.identity, name), name),
        )

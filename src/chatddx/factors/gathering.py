from collections.abc import Mapping
from typing import Annotated, Literal, Self, override
from uuid import UUID

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from .base import Component, Digest, Frozen, RefTo, Resolver, resolve
from .request import Skeleton
from .trial import Trial, TrialRef, replicates

# Dependency: every kind but a gathering, src/chatddx/factors/kinds.py:KINDS.
CENTER_KINDS = (
    "appendix",
    "canary_set",
    "case",
    "chunk.few_shot",
    "chunk.instructions",
    "chunk.output",
    "chunk.passthrough",
    "chunk.prompt",
    "chunk.reasoning",
    "chunk.sampling",
    "chunk.toolset",
    "chunk.translations",
    "compilation",
    "engine.local",
    "engine.remote",
    "expectation",
    "expectation_schema",
    "facts",
    "judge",
    "model.local",
    "model.remote",
    "scorer",
    "scoring",
    "skeleton",
    "tool",
    "trial",
)

CenterRef = Annotated[Digest, RefTo(*CENTER_KINDS)]
SeedingName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$")]


class Center(Frozen):
    component: CenterRef | None = None
    seed: int | None = None

    @model_validator(mode="after")
    def _one(self) -> Self:
        if (self.component is None) == (self.seed is None):
            raise ValueError("a center is a component or a seed")
        return self


class Seeding(Frozen):
    name: SeedingName
    seeds: int = Field(ge=1)
    repeats: SeedingName | None = None


def _seedings(seedings: tuple[Seeding, ...]) -> tuple[Seeding, ...]:
    seen: dict[str, Seeding] = {}
    for s in seedings:
        if s.name in seen:
            raise ValueError(f"the seeding {s.name} is named twice")
        if s.repeats is not None:
            repeated = seen.get(s.repeats)
            if repeated is None:
                raise ValueError(f"{s.name} repeats {s.repeats}, which isn't before it")
            if s.seeds > repeated.seeds:
                raise ValueError(f"{s.name} repeats more seeds than {s.repeats} has")
        seen[s.name] = s
    return seedings


Seedings = Annotated[
    tuple[Seeding, ...], AfterValidator(_seedings), Field(min_length=1)
]

# Policy: the shape of a review of a case, an original of three replicates under seeds
# drawn and a repeat of its third seed, which tells whether what it answered reproduces.
REVIEW: tuple[Seeding, ...] = (
    Seeding(name="original", seeds=3),
    Seeding(name="repeat", seeds=1, repeats="original"),
)

# Policy: the shape of a configuration's baseline on the World's baseline cases, an
# original of one replicate and a repeat of its seed, fewer than a review's as it spans
# many cases.
BASELINE: tuple[Seeding, ...] = (
    Seeding(name="original", seeds=1),
    Seeding(name="repeat", seeds=1, repeats="original"),
)


def fits(
    seeding: Seeding, trial: str, bound: Mapping[str, str], get: Resolver
) -> str | None:
    """Why a run of the trial can't take the seeding in a group whose other seedings
    hold the trials in `bound`, or None when it can; resolves the trial, and a repeat
    the trial it repeats."""
    ran = resolve(get, trial, Trial)
    if len(ran.seeds) != seeding.seeds:
        return f"ran {len(ran.seeds)} seeds, not {seeding.seeds}"
    if seeding.repeats is None:
        return None
    if seeding.repeats not in bound:
        return f"has no {seeding.repeats} to repeat"
    repeated = resolve(get, bound[seeding.repeats], Trial)
    skeleton = resolve(get, repeated.skeleton, Skeleton)
    seeds = replicates(skeleton, repeated.seeds[-seeding.seeds :])
    if repeated.model_copy(update={"seeds": seeds}).digest != trial:
        return f"ran other than {seeding.repeats}'s trial on its last seeds"
    return None


class Gathered(Frozen):
    group: int = Field(ge=0)
    seeding: SeedingName
    run: UUID
    trial: TrialRef


class Gathering(Component):
    kind: Literal["gathering"] = "gathering"
    center: Center
    seedings: Seedings
    gathered: tuple[Gathered, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _gathered(self) -> Self:
        order = {s.name: i for i, s in enumerate(self.seedings)}
        for g in self.gathered:
            if g.seeding not in order:
                raise ValueError(f"no seeding {g.seeding} to gather into")
        keys = [(g.group, order[g.seeding]) for g in self.gathered]
        if keys != sorted(set(keys)):
            raise ValueError("runs go by group, then by seeding in its order, once")
        if sorted({g for g, _ in keys}) != list(range(keys[-1][0] + 1)):
            raise ValueError("groups are numbered from 0 without gaps")
        if len({g.run for g in self.gathered}) != len(self.gathered):
            raise ValueError("a run is gathered once")
        return self

    def groups(self) -> list[dict[str, Gathered]]:
        held: list[dict[str, Gathered]] = [
            {} for _ in range(self.gathered[-1].group + 1)
        ]
        for g in self.gathered:
            held[g.group][g.seeding] = g
        return held

    @override
    def cross_check(self, get: Resolver) -> list[str]:
        problems: list[str] = []
        for i, group in enumerate(self.groups()):
            bound = {name: g.trial for name, g in group.items()}
            for s in self.seedings:
                if s.name in group and (why := fits(s, bound[s.name], bound, get)):
                    problems.append(f"group {i}'s {s.name} {why}")
        return problems

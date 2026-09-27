from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchOut,
    ConfigurationTrailIn,
)
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.entity_names import EntityName
from chatddx.runtime.resolution import Slices

SLICES: tuple[EntityName, ...] = (
    "instruction",
    "output",
    "coercion",
    "reasoning",
    "sampling",
    "toolset",
)

OPTIONAL: tuple[EntityName, ...] = ("toolset",)
NONE = "none"


@dataclass(frozen=True)
class Kept:
    configuration: str
    stack: str
    set: Mapping[str, str]
    label: str
    fingerprint: str
    seed: int | None


@dataclass(frozen=True, eq=False)
class Cell:
    configuration: ConfigurationBranchOut | None = None
    name: str = ""
    variations: Mapping[str, Any] = field(default_factory=dict[str, Any])
    stack: StackBranchOut | None = None

    def using(self, configuration: Any, name: str) -> "Cell":
        return replace(
            self,
            configuration=ConfigurationBranchOut.model_validate(configuration),
            name=name,
            variations={},
        )

    def on(self, stack: Any) -> "Cell":
        return replace(self, stack=StackBranchOut.model_validate(stack))

    @property
    def complete(self) -> bool:
        return self.configuration is not None and self.stack is not None

    @property
    def label(self) -> str:
        if not self.configuration:
            return ""

        set_ = "".join(
            f"+{entity}={self.set_name(entity)}"
            for entity in SLICES
            if entity in self.variations
        )
        return f"{self.name}{set_}"

    def set_name(self, entity: str) -> str:
        variation = self.variations[entity]
        return NONE if variation is None else variation.name

    @property
    def set_names(self) -> dict[str, str]:
        return {
            entity: self.set_name(entity)
            for entity in SLICES
            if entity in self.variations
        }

    def holds(self, entity: str, variation: Any) -> bool:
        assert self.configuration

        own = getattr(self.configuration.trail, entity)

        if variation is None:
            return own is None

        return own is not None and own.fingerprint == variation.trail.fingerprint

    def set(self, entity: str, variation: Any) -> "Cell":
        if variation is None and entity not in OPTIONAL:
            raise ValueError(
                f"a configuration always has a {entity}: only a toolset can be none"
            )

        variations = {
            held: kept for held, kept in self.variations.items() if held != entity
        }

        if not self.holds(entity, variation):
            variations[entity] = variation

        return replace(self, variations=variations)

    @property
    def slices(self) -> Slices:
        return Slices(**{entity: self.variation(entity) for entity in SLICES})

    @property
    def fingerprint(self) -> str:
        return ConfigurationTrailIn.model_validate(
            self.slices, from_attributes=True
        ).fingerprint

    def variation(self, entity: str) -> Any:
        assert self.configuration

        if entity in self.variations:
            variation = self.variations[entity]
            return None if variation is None else variation.trail

        return getattr(self.configuration.trail, entity)

    def kept(self, seed: int | None) -> Kept:
        assert self.configuration and self.stack

        return Kept(
            self.name,
            self.stack.name,
            self.set_names,
            self.label,
            self.fingerprint,
            seed,
        )

    def described(self, case: str, seed: int | None) -> str:
        assert self.stack
        seeded = f" (seed {seed})" if seed is not None else ""

        return f"{self.label} × {self.stack.name} × {case}{seeded}"

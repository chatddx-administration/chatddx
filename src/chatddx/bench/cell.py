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


@dataclass(frozen=True, eq=False)
class Cell:
    """
    A configuration and a stack, and any slice's variation held in place of
    the configuration's. A cell never changes: each change is another cell.
    """

    configuration: ConfigurationBranchOut | None = None
    name: str = ""
    variations: Mapping[str, Any] = field(default_factory=dict[str, Any])
    stack: StackBranchOut | None = None

    def using(self, configuration: Any, name: str) -> "Cell":
        """The configuration in the cell, as `name`, and nothing set in it."""
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
        """What is set in the cell in place of the configuration's, by name."""
        return {
            entity: self.set_name(entity)
            for entity in SLICES
            if entity in self.variations
        }

    def holds(self, entity: str, variation: Any) -> bool:
        """Whether `variation` is the configuration's own; None, no toolset."""
        assert self.configuration

        own = getattr(self.configuration.trail, entity)

        if variation is None:
            return own is None

        return own is not None and own.fingerprint == variation.trail.fingerprint

    def set(self, entity: str, variation: Any) -> "Cell":
        """`variation` held in place of the configuration's; None takes it out."""
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
        """The fingerprint of the configuration the cell comes to, set or not."""
        return ConfigurationTrailIn.model_validate(
            self.slices, from_attributes=True
        ).fingerprint

    def variation(self, entity: str) -> Any:
        assert self.configuration

        if entity in self.variations:
            variation = self.variations[entity]
            return None if variation is None else variation.trail

        return getattr(self.configuration.trail, entity)

    def described(self, case: str, seed: int | None) -> str:
        """What runs, as a run's conversation is described."""
        assert self.stack
        seeded = f" (seed {seed})" if seed is not None else ""

        return f"{self.label} × {self.stack.name} × {case}{seeded}"

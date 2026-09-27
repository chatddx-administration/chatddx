from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from chatddx.repo.entities.configuration.pydantic import (
    OPTIONAL,
    SLICES,
    ConfigurationBranchOut,
    ConfigurationTrailIn,
)
from chatddx.repo.entities.stack.pydantic import StackBranchOut
from chatddx.repo.entity_names import EntityName

NONE = "none"


def labelled(name: str, set_names: Mapping[str, str]) -> str:
    return name + "".join(
        f"+{entity}={set_names[entity]}" for entity in SLICES if entity in set_names
    )


class Made(Protocol):
    @property
    def trial(self) -> Any: ...

    @property
    def configuration_branch(self) -> Any: ...

    @property
    def stack_branch(self) -> Any: ...

    @property
    def instruction_branch(self) -> Any: ...

    @property
    def output_branch(self) -> Any: ...

    @property
    def coercion_branch(self) -> Any: ...

    @property
    def reasoning_branch(self) -> Any: ...

    @property
    def sampling_branch(self) -> Any: ...

    @property
    def toolset_branch(self) -> Any: ...


def set_in(made: Made) -> dict[EntityName, Any]:
    found: dict[EntityName, Any] = {
        entity: branch
        for entity in SLICES
        if (branch := getattr(made, f"{entity}_branch")) is not None
    }
    configuration = made.configuration_branch

    for entity in OPTIONAL:
        if (
            entity not in found
            and configuration is not None
            and getattr(configuration.trail, f"{entity}_id") is not None
            and getattr(made.trial.configuration, f"{entity}_id") is None
        ):
            found[entity] = None

    return found


def set_names_of(made: Made) -> dict[str, str]:
    return {
        entity: NONE if branch is None else branch.name
        for entity, branch in set_in(made).items()
    }


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

        return labelled(self.name, self.set_names)

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

    @property
    def set_ids(self) -> dict[str, int]:
        return {
            entity: variation.id
            for entity, variation in self.variations.items()
            if variation is not None
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
    def trail(self) -> ConfigurationTrailIn:
        return ConfigurationTrailIn.model_validate(
            {entity: self.variation(entity) for entity in SLICES},
            from_attributes=True,
        )

    @property
    def fingerprint(self) -> str:
        return self.trail.fingerprint

    def variation(self, entity: str) -> Any:
        assert self.configuration

        if entity in self.variations:
            variation = self.variations[entity]
            return None if variation is None else variation.trail

        return getattr(self.configuration.trail, entity)

    def described(self, case: str, seed: int | None) -> str:
        assert self.stack
        seeded = f" (seed {seed})" if seed is not None else ""

        return f"{self.label} × {self.stack.name} × {case}{seeded}"

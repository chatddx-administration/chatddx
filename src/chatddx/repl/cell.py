from typing import Any

from chatddx.repo.entities.configuration.pydantic import ConfigurationBranchOut
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


class Cell:
    def __init__(self):
        self.configuration: ConfigurationBranchOut | None = None
        self.name: str = ""
        self.variations: dict[str, Any] = {}
        self.stack: StackBranchOut | None = None

    def put(self, configuration: Any, name: str) -> None:
        self.configuration = ConfigurationBranchOut.model_validate(configuration)
        self.name = name
        self.variations = {}

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

    def set(self, entity: str, variation: Any) -> None:
        """Hold `variation` in place of the configuration's; None takes it out."""
        assert self.configuration

        if variation is None and entity not in OPTIONAL:
            raise ValueError(
                f"a configuration always has a {entity}: only a toolset can be none"
            )

        own = getattr(self.configuration.trail, entity)
        same = (
            own is None
            if variation is None
            else own is not None and own.fingerprint == variation.trail.fingerprint
        )

        if same:
            _ = self.variations.pop(entity, None)
        else:
            self.variations[entity] = variation

    @property
    def slices(self) -> Slices:
        return Slices(**{entity: self.variation(entity) for entity in SLICES})

    def variation(self, entity: str) -> Any:
        assert self.configuration

        if entity in self.variations:
            variation = self.variations[entity]
            return None if variation is None else variation.trail

        return getattr(self.configuration.trail, entity)

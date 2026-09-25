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
    """
    A configuration joined to a stack (datamodel.md §2), called what it
    was called when it was put in, and the variations `set` put in it in
    place of the configuration's: None where it took an optional slice out.
    """

    def __init__(self):
        self.configuration: ConfigurationBranchOut | None = None
        self.name: str = ""
        self.variations: dict[str, Any] = {}
        self.stack: StackBranchOut | None = None

    def put(self, configuration: Any, name: str) -> None:
        """Put a configuration in as it is: what was set was set in another."""
        self.configuration = ConfigurationBranchOut.model_validate(configuration)
        self.name = name
        self.variations = {}

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
        return f"{self.name}{set_}"

    def set_name(self, entity: str) -> str:
        """The name of the variation set in the cell, or none."""
        variation = self.variations[entity]
        return NONE if variation is None else variation.name

    @property
    def slices(self) -> Slices:
        """The cell's variations: those set, and the configuration's."""
        return Slices(**{entity: self.variation(entity) for entity in SLICES})

    def variation(self, entity: str) -> Any:
        assert self.configuration

        if entity in self.variations:
            variation = self.variations[entity]
            return None if variation is None else variation.trail

        return getattr(self.configuration.trail, entity)

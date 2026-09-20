# TODO: Get rid of this module.
from typing import get_args

from chatddx.repo.registry import EntityName

# The relations the flat agent form inlines as subforms of their own. An
# agent's instruction is a relation as well, but it is rendered as one
# textarea on the agent itself, so it is not one of these.
agent_relations: list[EntityName] = [
    "connection",
    "sampling_params",
    "output_type",
    "tool_group",
]

all_entities: tuple[EntityName, ...] = get_args(EntityName.__value__)

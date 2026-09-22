# TODO: Get rid of this module.
from typing import get_args

from chatddx.repo.entity_names import EntityName

agent_relations: list[EntityName] = [
    "connection",
    "sampling_params",
    "output_type",
    "tool_group",
]

all_entities: tuple[EntityName, ...] = get_args(EntityName.__value__)

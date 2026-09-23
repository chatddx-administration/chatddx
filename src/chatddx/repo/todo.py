# TODO: Get rid of this module.
from typing import get_args

from chatddx.repo.entity_names import EntityName

all_entities: tuple[EntityName, ...] = get_args(EntityName.__value__)

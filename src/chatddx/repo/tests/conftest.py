from pathlib import Path

import pytest

from chatddx.core import settings
from chatddx.repo.inventories import InventoryTrailSchema
from chatddx.repo.parsers.inventory import parse
from chatddx.repo.shufflers import inventory


@pytest.fixture
def trails() -> InventoryTrailSchema:
    """The test inventory's trails, parsed without a database to own them."""
    return inventory.trail_schema(
        parse(Path(__file__).parent / settings.TEST_INVENTORY_PATH)
    )

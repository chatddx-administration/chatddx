import pytest

from chatddx.repo.inventories import InventoryTrailSchema, ParsedInventory
from chatddx.repo.shufflers import inventory


@pytest.fixture
def trails(test_inventory: ParsedInventory) -> InventoryTrailSchema:
    """The test inventory's trails, with no database to own them."""
    return inventory.trail_schema(test_inventory)

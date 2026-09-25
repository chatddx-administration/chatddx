import pytest

from chatddx.repo.inventories import InventoryTrailIn, ParsedInventory
from chatddx.repo.store import inventory


@pytest.fixture
def trails(test_inventory: ParsedInventory) -> InventoryTrailIn:
    return inventory.trails_in(test_inventory)

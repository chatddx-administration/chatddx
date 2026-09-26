import pytest

from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_identity
from chatddx.repo.inventories import InventoryTrailIn, ParsedInventory
from chatddx.repo.store import inventory


@pytest.fixture
def owner() -> IdentityModel:
    return ensure_identity("alice")


@pytest.fixture
def other_owner() -> IdentityModel:
    return ensure_identity("other")


@pytest.fixture
def trails(test_inventory: ParsedInventory) -> InventoryTrailIn:
    return inventory.trails_in(test_inventory)

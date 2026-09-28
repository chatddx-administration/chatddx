import pytest

from chatddx.core import settings
from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.repo.inventories import InventoryBranchOut, InventoryTrailIn
from chatddx.repo.store.inventory import owned_inventory

pytestmark = pytest.mark.django_db

COUNTS = {
    "machine": 3,
    "os": 3,
    "llm": 2,
    "serving": 5,
    "client": 2,
    "stack": 5,
    "tool": 3,
    "toolset": 2,
    "instruction": 3,
    "output": 5,
    "coercion": 5,
    "reasoning": 9,
    "sampling": 5,
    "configuration": 12,
    "case": 2,
    "scorer": 4,
}


def test_trail_schema(trails: InventoryTrailIn):
    assert {e: len(getattr(trails, e)) for e in ENTITY_NAMES} == COUNTS


def test_a_committed_inventory_reads_back_as_models_and_specs():
    models = owned_inventory(settings.ARCHIVE_IDENTITY_NAME)
    specs = InventoryBranchOut.model_validate(models)

    assert {e: len(models[e]) for e in ENTITY_NAMES} == COUNTS
    assert {e: len(getattr(specs, e)) for e in ENTITY_NAMES} == COUNTS

    stack = specs.stack["qwen3-8b-awq@malborg"]

    assert stack.details.served_name == "Qwen/Qwen3-8B-AWQ"
    assert stack.trail.host_os is not None
    assert stack.tags == ["rtx-5090"]

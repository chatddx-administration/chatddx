import pytest

from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.repo.inventories import (
    InventoryBranchModel,
    InventoryBranchOut,
    InventoryFormDataOut,
    InventoryTrailIn,
)

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


def test_trail_schema(inventory_fixture_ti: InventoryTrailIn):
    assert {e: len(getattr(inventory_fixture_ti, e)) for e in ENTITY_NAMES} == COUNTS


def test_a_committed_inventory_reads_back_as_models_specs_and_form_data(
    inventory_fixture_bm: InventoryBranchModel,
    inventory_fixture_bo: InventoryBranchOut,
    inventory_fixture_fdo: InventoryFormDataOut,
):
    assert {e: len(inventory_fixture_bm[e]) for e in ENTITY_NAMES} == COUNTS
    assert {e: len(getattr(inventory_fixture_bo, e)) for e in ENTITY_NAMES} == COUNTS

    stack = inventory_fixture_bo.stack["qwen3-8b-awq@malborg"]

    assert stack.details.served_name == "Qwen/Qwen3-8B-AWQ"
    assert stack.trail.host_os is not None
    assert stack.tags == ["rtx-5090"]
    assert {e: len(getattr(inventory_fixture_fdo, e)) for e in ENTITY_NAMES} == COUNTS

    tool = inventory_fixture_fdo.tool["web_search"]

    assert (tool.name, tool.tool_name) == ("web_search", "web_search")
    assert inventory_fixture_fdo.stack["qwen3-8b-awq@pelle"].endpoint == (
        "http://pelle.km:12009/v1/"
    )

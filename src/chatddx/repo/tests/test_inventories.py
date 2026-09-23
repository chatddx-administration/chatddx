import pytest

from chatddx.repo.inventories import (
    InventoryBranchModel,
    InventoryBranchSpec,
    InventoryFormDataOut,
    InventoryTrailSchema,
)
from chatddx.repo.todo import all_entities

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.asyncio,
]

# the test inventory: the inventory's records, and two cases of its own
COUNTS = {
    "machine": 3,
    "os": 3,
    "model": 2,
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
}


async def test_trail_schema(inventory_fixture_ts: InventoryTrailSchema):
    assert {e: len(getattr(inventory_fixture_ts, e)) for e in all_entities} == COUNTS


async def test_branch_models(inventory_fixture_bm: InventoryBranchModel):
    assert {e: len(inventory_fixture_bm[e]) for e in all_entities} == COUNTS


async def test_branch_specs(inventory_fixture_bs: InventoryBranchSpec):
    assert {e: len(getattr(inventory_fixture_bs, e)) for e in all_entities} == COUNTS

    stack = inventory_fixture_bs.stack["qwen3-8b-awq@malborg"]

    # a spec holds the branch's details beside its content
    assert stack.details.served_name == "Qwen/Qwen3-8B-AWQ"
    assert stack.target.host_os is not None
    assert stack.tags == ["rtx-5090"]


async def test_form_data_out(inventory_fixture_fdo: InventoryFormDataOut):
    assert {e: len(getattr(inventory_fixture_fdo, e)) for e in all_entities} == COUNTS

    tool = inventory_fixture_fdo.tool["web_search"]

    # a form's `name` is the branch's; the tool's own is `tool_name`
    assert (tool.name, tool.tool_name) == ("web_search", "web_search")
    assert inventory_fixture_fdo.stack["qwen3-8b-awq@pelle"].endpoint == (
        "http://pelle.km:12009/v1/"
    )

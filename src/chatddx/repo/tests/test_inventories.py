import pytest

from chatddx.repo.inventories import (
    InventoryBranchModel,
    InventoryBranchSpec,
    InventoryFormDataOut,
    InventoryTrailSchema,
)

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.asyncio,
]


async def test_trail_schema(inventory_fixture_ts: InventoryTrailSchema):

    assert len(inventory_fixture_ts.agent) == 4
    assert len(inventory_fixture_ts.connection) == 3


async def test_branch_models(inventory_fixture_bm: InventoryBranchModel):

    assert len(inventory_fixture_bm["agent"]) == 4
    assert len(inventory_fixture_bm["connection"]) == 3


async def test_branch_specs(inventory_fixture_bs: InventoryBranchSpec):

    assert len(inventory_fixture_bs.agent) == 4
    assert len(inventory_fixture_bs.connection) == 3


async def test_form_data_out(inventory_fixture_fdo: InventoryFormDataOut):

    assert len(inventory_fixture_fdo.agent) == 4
    assert len(inventory_fixture_fdo.connection) == 3

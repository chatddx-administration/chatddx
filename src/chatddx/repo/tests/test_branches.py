import pytest

from chatddx.core.models import IdentityModel
from chatddx.repo.inventories import InventoryBranchModel
from chatddx.repo.shufflers.branch import get_branch_async


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_model_from_schema(
    inventory_fixture_bm: InventoryBranchModel,
    owner: IdentityModel,
):
    _ = inventory_fixture_bm
    branch_model = await get_branch_async(
        entity_name="agent",
        branch_name="agent-1",
        owner_name=owner.name,
    )
    assert branch_model is not None
    assert branch_model.id is not None
    assert branch_model.name == "agent-1"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_cases_from_dir(
    inventory_fixture_bm: IdentityModel,
    owner: IdentityModel,
):
    branch_model = await get_branch_async(
        entity_name="case",
        branch_name="case-1",
        owner_name=owner.name,
    )

    assert branch_model.name == "case-1"
    assert branch_model.target.payload == "case payload 1"

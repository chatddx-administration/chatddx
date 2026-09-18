import pytest

from chatddx.repo.inventories import InventoryBranchSpec

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.asyncio
async def test_case_1(inventory_fixture_bs: InventoryBranchSpec):
    case_1 = inventory_fixture_bs.case["case-1"]
    assert case_1.name == "case-1"
    assert case_1.target.payload == "case payload 1"
    assert case_1.tags == ["tag-1", "tag-2"]
    assert case_1.target.expects[0].payload == "expect payload 1 for scorer a"
    assert case_1.target.expects[0].scorer.command == "scorer-a command"

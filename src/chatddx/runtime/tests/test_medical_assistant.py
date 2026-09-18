import json
from typing import Any

import pytest

from chatddx.core import settings
from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.runtime.runners import run_from_spec

pytestmark = pytest.mark.network


def get_case_and_expect(name: str) -> tuple[str, dict[str, Any]]:
    data_path = settings.INVENTORY_PATH / f"chatddx/cases/case_{name}.txt"
    expects_path = settings.INVENTORY_PATH / f"chatddx/cases/expect_{name}.json"

    with data_path.open("r") as f:
        case = f.read()

    with expects_path.open("r") as f:
        expect = json.load(f)

    return case, expect


@pytest.mark.asyncio
@pytest.mark.django_db()
@pytest.mark.parametrize(
    "case_name",
    [
        "a",
        "b",
    ],
)
async def test_qwen3_baseline(
    inventory_fixture_bs: InventoryBranchSpec, case_name: str
):
    agent = inventory_fixture_bs.agent[
        "qwen3-8b management_plan_v1 seed-locked disable-thinking"
    ]
    case, expect = get_case_and_expect(case_name)

    result = await run_from_spec(agent.target, case)
    print(json.dumps(result.output, indent=2))

    assert result.output == expect

from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from pydantic_ai import AgentRunResult

from chatddx.core import settings
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.parsers.inventory import parse
from chatddx.runtime.resolution import Resolution
from chatddx.runtime.run import Run, invalid

type Cell = Callable[..., Resolution]
type Ran = Callable[[Run], Coroutine[Any, Any, AgentRunResult[Any]]]

pytestmark = [pytest.mark.network, pytest.mark.asyncio]

STACK = "qwen3-8b-awq@pelle"


@pytest.fixture(scope="module")
def live_inventory() -> ParsedInventory:
    return parse(settings.INVENTORY_PATH / "inventory.toml")


@pytest.mark.parametrize("case_name", ["DutchFall10w", "Dutchfall11w"])
async def test_qwen3_management_plan(
    cell: Cell, ran: Ran, live_inventory: ParsedInventory, case_name: str
):
    resolution = cell("plan", STACK, reasoning="off")
    case, _ = live_inventory.case[case_name]
    assert resolution.coercion is not None

    result = await ran(Run(resolution, case.vignette, seed=0))

    assert invalid(resolution.coercion.schema, result.output) is None
    assert resolution.output.view("differential", result.output)

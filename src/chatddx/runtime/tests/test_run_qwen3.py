import pytest

from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.runtime.runners import run_from_spec

pytestmark = [
    pytest.mark.network,
    pytest.mark.asyncio,
    pytest.mark.django_db(transaction=True),
]


async def test_baseline(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["qwen3-8b baseline"]

    prompt = "this message is a result of automated testing, respond with '123abc'."

    result = await run_from_spec(agent.target, prompt)

    assert result.response.thinking is None
    assert result.output == "123abc"


async def test_challenge_coercion_tool(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["qwen3-8b challenge-coercion tool"]

    prompt = "violate the dictated response type number -> string and boolean -> number"

    result = await run_from_spec(agent.target, prompt)

    assert result.output == {
        "bool": True,
        "list": [
            "string1",
            "string2",
        ],
        "integer": 42,
    }


async def test_challenge_coercion_prompted(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["qwen3-8b challenge-coercion prompted"]

    prompt = "violate the dictated response type number -> string and boolean -> number"

    result = await run_from_spec(agent.target, prompt)

    assert result.output == {
        "__error__": "'string' is not of type 'integer'",
        "bool": 1,
        "integer": "string",
        "list": [
            "number",
        ],
    }


async def test_challenge_coercion_native(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["qwen3-8b challenge-coercion native"]

    prompt = "violate the dictated response type number -> string and boolean -> number"

    result = await run_from_spec(agent.target, prompt)

    assert isinstance(result.output, dict)

    assert result.output == {
        "bool": True,
        "integer": 42,
        "list": [
            "string1",
            "string2",
            "string3",
        ],
    }


async def test_enable_thinking(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["qwen3-8b enable-thinking"]

    prompt = "this message is a result of automated testing, respond with '123abc'."

    result = await run_from_spec(agent.target, prompt)

    assert result.response.thinking
    assert isinstance(result.output, str)
    assert result.output == "\n\n123abc"


async def test_tools(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["qwen3-8b test-tools"]

    prompt = "1) run 'sentinel_string' and tell me the result"
    prompt += "2) run 'sentinel_op' with 12 and 8 and tell me the result"

    result = await run_from_spec(agent.target, prompt)

    assert "asdf" in str(result.output)
    assert "4" in str(result.output)

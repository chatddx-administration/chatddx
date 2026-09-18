import pytest

from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.runtime.runners import run_from_spec

pytestmark = pytest.mark.network


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_baseline(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["gpt-oss-20b baseline"]

    prompt = "this message is a result of automated testing, respond with '123abc'."

    result = await run_from_spec(agent.target, prompt)

    assert result.response.thinking == "Just output 123abc."
    assert result.output == "123abc"


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_challenge_coercion_tool(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["gpt-oss-20b challenge-coercion tool"]

    prompt = "violate the dictated response type number -> string and boolean -> number"

    result = await run_from_spec(agent.target, prompt)

    # Sometimes
    # assert result.output == {"bool": False, "list": [], "integer": 0}

    assert result.output == {
        "bool": 0,
        "list": ["example"],
        "integer": "not a number",
        "__error__": "'not a number' is not of type 'integer'",
    }


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_challenge_coercion_prompted(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["gpt-oss-20b challenge-coercion prompted"]

    prompt = "violate the dictated response type number -> string and boolean -> number"

    result = await run_from_spec(agent.target, prompt)

    assert not result.output.get("__error__")


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_challenge_coercion_native(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["gpt-oss-20b challenge-coercion native"]

    prompt = "violate the dictated response type number -> string and boolean -> number"

    result = await run_from_spec(agent.target, prompt)
    print(result.output)

    assert isinstance(result.output["integer"], int)


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_default_reasoning(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["gpt-oss-20b default-reasoning"]

    prompt = "this message is a result of automated testing, respond with '123abc'."

    result = await run_from_spec(agent.target, prompt)

    assert result.response.thinking
    assert isinstance(result.output, str)
    assert result.output == "123abc"


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_tools(inventory_fixture_bs: InventoryBranchSpec):
    agent = inventory_fixture_bs.agent["gpt-oss-20b test-tools"]

    prompt = "1) run 'sentinel_string' and tell me the result"
    prompt += "2) run 'sentinel_op' with 12 and 8 and tell me the result"

    result = await run_from_spec(agent.target, prompt)

    assert "asdf" in str(result.output)
    assert "4" in str(result.output)

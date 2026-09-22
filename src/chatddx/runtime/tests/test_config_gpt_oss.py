import pytest

from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.runtime.builder import build_agent, build_output_type

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.django_db(transaction=True),
]


async def test_baseline(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["gpt-oss-20b baseline"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)

    assert agent.model_settings.get("logit_bias") == None
    assert agent.model_settings.get("seed") == 0
    assert agent.model_settings.get("openai_reasoning_effort") == "low"


async def test_challenge_coercion_tool(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["gpt-oss-20b challenge-coercion tool"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0


async def test_challenge_coercion_prompted(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["gpt-oss-20b challenge-coercion prompted"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0


async def test_challenge_coercion_native(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["gpt-oss-20b challenge-coercion native"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0


async def test_default_reasoning(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["gpt-oss-20b default-reasoning"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0


async def test_tools(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["gpt-oss-20b test-tools"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0

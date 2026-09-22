import pytest

from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.runtime.builder import build_agent, build_output_type
from chatddx.utils import dig

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.django_db(transaction=True),
]


async def test_baseline(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b baseline"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0
    assert (
        dig(
            agent.model_settings,
            "extra_body",
            "chat_template_kwargs",
            "enable_thinking",
        )
        is False
    )


async def test_challenge_coercion_tool(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b challenge-coercion tool"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0


async def test_challenge_coercion_prompted(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b challenge-coercion prompted"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0


async def test_challenge_coercion_native(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b challenge-coercion native"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0


async def test_enable_thinking(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b enable-thinking"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0


async def test_tools(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b test-tools"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings
    assert not callable(agent.model_settings)
    assert agent.model_settings.get("seed") == 0

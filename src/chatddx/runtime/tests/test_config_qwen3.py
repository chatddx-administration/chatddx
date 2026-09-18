import pytest

from chatddx.repo.inventories import InventoryBranchSpec
from chatddx.runtime.builder import build_agent, build_output_type


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_baseline(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b baseline"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)
    settings = agent.model_settings

    assert settings.get("seed") == 0
    assert (
        settings.get("extra_body")["chat_template_kwargs"]["enable_thinking"] == False
    )


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_challenge_coercion_tool(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b challenge-coercion tool"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings is not None
    assert agent.model_settings.get("seed") == 0


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_challenge_coercion_prompted(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b challenge-coercion prompted"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings is not None
    assert agent.model_settings.get("seed") == 0


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_challenge_coercion_native(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b challenge-coercion native"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings is not None
    assert agent.model_settings.get("seed") == 0


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_enable_thinking(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b enable-thinking"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)
    settings = agent.model_settings

    assert settings.get("seed") == 0


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_tools(inventory_fixture_bs: InventoryBranchSpec):
    branch = inventory_fixture_bs.agent["qwen3-8b test-tools"]

    output_type = build_output_type(branch.target)
    agent = build_agent(branch.target, output_type)

    assert agent.model_settings is not None
    assert agent.model_settings.get("seed") == 0

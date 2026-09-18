from chatddx.repo.inventories import InventoryTrailSchema


def test_properties(inventory_fixture_ts: InventoryTrailSchema):
    agent_1 = inventory_fixture_ts.agent["agent-1"]
    assert agent_1.tool_group

    fingerprint = agent_1.fingerprint

    agent_1_ = inventory_fixture_ts.agent["agent-1"]
    assert agent_1_.fingerprint == fingerprint

    agent_1_.instructions += "a"
    assert agent_1_.fingerprint != fingerprint

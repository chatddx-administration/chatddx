from decimal import Decimal
from pathlib import Path

import pytest

from chatddx.core.choices import ToolChoices
from chatddx.repo.inventories import InventoryTrailSchema
from chatddx.repo.parsers.inventory import ParseError, parse


def test_inventory_search():
    pass


def test_properties(inventory_fixture_ts: InventoryTrailSchema):
    agent_1 = inventory_fixture_ts.agent["agent-1"]
    assert agent_1.instructions == "hello 1"
    assert agent_1.tool_group
    assert agent_1.tool_group.instructions == "Tool group instructions 1"
    assert agent_1.tool_group.tools[0].type == ToolChoices.FUNCTION


def test_some_properties(inventory_fixture_ts: InventoryTrailSchema):
    some_connection = inventory_fixture_ts.connection["some-connection"]
    assert some_connection.model == "Some/model"
    some_case = inventory_fixture_ts.case["some-case"]
    assert some_case.payload == "some case payload"


def test_extended_inventories(inventory_fixture_ts: InventoryTrailSchema):
    agent_1 = inventory_fixture_ts.agent["some-agent"]
    assert agent_1.instructions == "some instructions"
    assert agent_1.tool_group.instructions == "some tool group instructions"


def test_merged_properties(inventory_fixture_ts: InventoryTrailSchema):
    agent_2 = inventory_fixture_ts.agent["agent-2"]
    assert agent_2.instructions == "hello 2"
    assert agent_2.sampling_params
    assert agent_2.sampling_params.temperature == Decimal("0.7")
    assert agent_2.sampling_params.max_tokens == 150
    assert agent_2.sampling_params.seed == 0
    assert agent_2.sampling_params.stop_sequences == ["\\n\\n", "END"]


def test_extended_records(inventory_fixture_ts: InventoryTrailSchema):
    agent_3 = inventory_fixture_ts.agent["agent-3"]
    assert agent_3.instructions == "hello 3"
    assert agent_3.sampling_params
    assert agent_3.tool_group
    assert agent_3.tool_group.instructions == "Tool group instructions 1"
    assert agent_3.tool_group.tools[0].type == ToolChoices.FUNCTION


def test_infrec_file():
    with pytest.raises(ParseError):
        infrec = parse(path=Path(__file__).parent / "data/infrec-1.toml")
        assert infrec


@pytest.mark.skip(reason="Infinite recursion detection is temporarily broken")
def test_infrec_record():
    infrec = parse(path=Path(__file__).parent / "data/infrec-4.toml")

    infrec_1 = infrec.agent["agent-1"]
    assert infrec_1.instructions == "agent 1"

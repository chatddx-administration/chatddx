from decimal import Decimal
from pathlib import Path

import pytest

from chatddx.core.choices import ToolChoices
from chatddx.registry.main import parse_registry
from chatddx.registry.schemas import ParseError
from chatddx.repo.trail_schemas import TrailRegistry

registry: TrailRegistry = parse_registry(
    path=Path(__file__).parent / "data/test-registry.toml",
    schema=TrailRegistry,
)


def test_properties():
    agent_1 = registry.agent["agent-1"]
    assert agent_1.instructions == "hello 1"
    assert agent_1.tool_group
    assert agent_1.tool_group.instructions == "use these tools"
    assert agent_1.tool_group.tools[0].type == ToolChoices.FUNCTION


def test_some_properties():
    some_connection = registry.connection["some-connection"]
    assert some_connection.model == "Some/model"


def test_extended_registries():
    agent_1 = registry.agent["some-agent"]
    assert agent_1.instructions == "some instructions"
    assert agent_1.tool_group.instructions == "some tool group instructions"


def test_merged_properties():
    agent_2 = registry.agent["agent-2"]
    assert agent_2.instructions == "hello 2"
    assert agent_2.sampling_params
    assert agent_2.sampling_params.temperature == Decimal("0.7")
    assert agent_2.sampling_params.max_tokens == 150
    assert agent_2.sampling_params.seed == 0
    assert agent_2.sampling_params.stop_sequences == ["\\n\\n", "END"]


def test_extended_records():
    agent_3 = registry.agent["agent-3"]
    assert agent_3.instructions == "hello 3"
    assert agent_3.sampling_params
    assert agent_3.tool_group
    assert agent_3.tool_group.instructions == "use these tools"
    assert agent_3.tool_group.tools[0].type == ToolChoices.FUNCTION


def test_infrec_file():
    with pytest.raises(ParseError):
        infrec_registry: TrailRegistry = parse_registry(
            path=Path(__file__).parent / "data/infrec-1.toml",
            schema=TrailRegistry,
        )
        assert infrec_registry


def test_infrec_record():
    infrec_registry: TrailRegistry = parse_registry(
        path=Path(__file__).parent / "data/infrec-4.toml",
        schema=TrailRegistry,
    )

    infrec_1 = infrec_registry.agent["agent-1"]
    assert infrec_1.instructions == "agent 1"

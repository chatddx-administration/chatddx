from pathlib import Path

from chatddx.registry.main import parse_registry
from chatddx.repo.trail_schemas import TrailRegistry

registry: TrailRegistry = parse_registry(
    path=Path(__file__).parent / "data/test-registry.toml",
    schema=TrailRegistry,
)


def test_properties():
    agent_1 = registry.agent["agent-1"]
    assert agent_1.tool_group

    fingerprint = agent_1.fingerprint

    agent_1_ = registry.agent["agent-1"]
    assert agent_1_.fingerprint == fingerprint

    agent_1_.instructions += "a"
    assert agent_1_.fingerprint != fingerprint

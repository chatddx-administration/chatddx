"""
What the registry promises: the class of a thing says which entity it is,
and an entity carries only what it declares.
"""

from pathlib import Path

import pytest

from chatddx.repo.bundles import (
    ALL_ENTITIES,
    ALL_VIEWS,
    RegistryCollisionError,
    _index_by_class,
    entity_of,
    view_of,
)
from chatddx.repo.entities.agent.django import (
    Agent,
    AgentBranchModel,
    AgentTrailModel,
    SharedAgent,
)
from chatddx.repo.entities.agent.pydantic import AgentFormDataOut, AgentTrailSchema
from chatddx.repo.entities.case.django import Case, SharedCase
from chatddx.repo.entities.case.pydantic import CaseBranchDetails
from chatddx.repo.entities.super_agent.django import SharedSuperAgent, SuperAgent
from chatddx.repo.entities.super_agent.pydantic import SuperAgentFormDataOut
from chatddx.repo.families.pydantic import BranchSchemaDetails
from chatddx.repo.parsers.inventory import parse
from chatddx.repo.registry import AGENT, CASE
from chatddx.repo.todo import all_entities


def test_a_view_is_not_an_entity():
    """
    An agent is one entity however many forms render it, so nothing has to
    be declared in a particular order to keep the two apart.
    """
    assert "super_agent" not in all_entities
    assert AGENT.trail_model is AgentTrailModel

    for cls in (AgentTrailModel, AgentBranchModel, AgentTrailSchema):
        assert entity_of(cls) is AGENT


@pytest.mark.parametrize(
    "proxy", [Agent, SharedAgent, SuperAgent, SharedSuperAgent]
)
def test_every_agent_proxy_answers_agent(proxy: type):
    """
    `SuperAgent` used to answer 'super_agent' and `SharedSuperAgent` 'agent',
    because one was a registered member and the other fell through the MRO.
    The name reaches `ensure_tag`, so the two siloed tags differently.
    """
    assert entity_of(proxy) is AGENT
    assert entity_of(proxy).name == "agent"


def test_a_proxy_keeps_its_own_view():
    """
    Which entity a proxy belongs to and which form renders it are different
    questions, and the flat agent form is the reason they are.
    """
    assert view_of(SuperAgent).form_data_out is SuperAgentFormDataOut
    assert view_of(SharedSuperAgent).form_data_out is SuperAgentFormDataOut
    assert view_of(Agent).form_data_out is AgentFormDataOut

    # both views, one entity
    assert view_of(SuperAgent).entity is view_of(Agent).entity

    # anything that is not a registered proxy falls back to the entity's own
    assert view_of(AgentBranchModel).form_data_out is AgentFormDataOut


def test_a_case_proxy_answers_case():
    for proxy in (Case, SharedCase):
        assert entity_of(proxy) is CASE


def test_two_entities_may_not_claim_one_class():
    """
    The index used to resolve a collision by declaration order, silently.
    """
    with pytest.raises(RegistryCollisionError, match="AgentBranchSchema"):
        _ = _index_by_class((AGENT, AGENT), "members", "entity")


def test_every_entity_has_a_view_of_its_name():
    view_names = {view.name for view in ALL_VIEWS}

    for entity in ALL_ENTITIES:
        assert entity.name in view_names
        assert view_of(entity.name).entity is entity


def test_only_a_case_carries_expects():
    assert "expects" in CASE.branch_details.model_fields
    assert CASE.branch_details is CaseBranchDetails

    for entity in ALL_ENTITIES:
        if entity is CASE:
            continue
        assert entity.branch_details is BranchSchemaDetails
        assert "expects" not in entity.branch_details.model_fields


def test_expects_on_a_non_case_is_an_error_not_a_shrug():
    """
    `expects` on an agent used to be accepted by the shared details model and
    then dropped, because only a case ever read it back.
    """
    with pytest.raises(KeyError, match="expects"):
        _ = parse(path=Path(__file__).parent / "data/expects-on-an-agent.toml")

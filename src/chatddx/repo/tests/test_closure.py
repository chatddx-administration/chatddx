"""
The guarantee: a trail in an owner's possession has a branch of theirs on
it, however indirectly they came to possess it.

An owner possesses a trail directly when they have a branch on it, and
indirectly when a trail they possess points at it -- an agent's connection,
a tool group's tools, an expectation's scorer. `commit_closure` is what
makes the second case hold, and what these check.
"""

from typing import Any

import pytest

from chatddx.core.choices import ProviderChoices, ToolChoices
from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_tag
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.agent.pydantic import AgentTrailSchema
from chatddx.repo.entities.connection.pydantic import ConnectionTrailSchema
from chatddx.repo.entities.expect.pydantic import ExpectTrailSchema
from chatddx.repo.entities.scorer.pydantic import ScorerTrailSchema
from chatddx.repo.entities.tool.pydantic import ToolTrailSchema
from chatddx.repo.entities.tool_group.pydantic import ToolGroupTrailSchema
from chatddx.repo.families.django import TrailModel
from chatddx.repo.families.pydantic import BranchSchemaDetails
from chatddx.repo.names import resolve_branch_name
from chatddx.repo.shufflers.branch import (
    commit,
    get_branch_model,
    select_branch_models,
)
from chatddx.repo.todo import all_entities
from chatddx.repo.utils import trail_closure

pytestmark = pytest.mark.django_db(transaction=True)


def branches_on(trail: TrailModel, owner_name: str):
    return entity_of(trail).branch_model.objects.filter(
        target=trail,
        owner__name=owner_name,
    )


def dangling_trails(owner_name: str) -> list[TrailModel]:
    """
    Every trail `owner_name` possesses indirectly and has no branch on. The
    guarantee is that this is empty.
    """
    dangling: list[TrailModel] = []

    for entity_name in all_entities:
        for branch_model in select_branch_models(entity_name, owner_name):
            for trail in trail_closure(branch_model.target):
                if not branches_on(trail, owner_name).exists():
                    dangling.append(trail)

    return dangling


def an_agent(instructions: str = "an agent nobody named the parts of"):
    """
    An agent whose whole closure is new and unnamed: four relations, one of
    them with two tools of its own.
    """
    return AgentTrailSchema(
        instructions=instructions,
        connection=ConnectionTrailSchema(
            provider=ProviderChoices.VLLM,
            model="Test/closure",
            endpoint="http://closure.example.com/v1/",  # pyright: ignore[reportArgumentType]
        ),
        tool_group=ToolGroupTrailSchema(
            instructions="tools of an agent nobody named the parts of",
            tools=[
                ToolTrailSchema(command="closure-tool-1", type=ToolChoices.FUNCTION),
                ToolTrailSchema(command="closure-tool-2", type=ToolChoices.FUNCTION),
            ],
        ),
    )


def commit_agent(owner_name: str, name: str = "closure-agent", **kwargs: Any) -> bool:
    return commit(
        trail=an_agent(**kwargs),
        branch_details=BranchSchemaDetails(name=name, owner=owner_name),
    )


def test_a_commit_leaves_nothing_in_its_closure_branchless(owner: IdentityModel):
    assert commit_agent(owner.name)

    agent = get_branch_model("agent", owner.name, "closure-agent")
    closure = trail_closure(agent.target)

    # connection, sampling params, output type, tool group, two tools
    assert len(closure) == 6

    for trail in closure:
        assert branches_on(trail, owner.name).count() == 1

    assert dangling_trails(owner.name) == []


def test_a_branch_made_for_the_closure_is_named_by_the_resolver(
    owner: IdentityModel,
):
    assert commit_agent(owner.name)

    agent = get_branch_model("agent", owner.name, "closure-agent")
    connection = agent.target.connection

    made = branches_on(connection, owner.name).get()

    assert made.name == resolve_branch_name("connection", connection.fingerprint)
    assert made.name == f"connection {connection.fingerprint[:6]}"


def test_a_trail_the_owner_already_has_a_branch_on_is_left_alone(
    owner: IdentityModel,
):
    agent_schema = an_agent()

    assert commit(
        trail=agent_schema.connection,
        branch_details=BranchSchemaDetails(name="my connection", owner=owner.name),
    )

    assert commit_agent(owner.name)

    agent = get_branch_model("agent", owner.name, "closure-agent")
    connection = agent.target.connection

    # the name they chose, and no second branch beside it
    assert [b.name for b in branches_on(connection, owner.name)] == ["my connection"]


def test_committing_the_same_agent_again_makes_no_further_branches(
    owner: IdentityModel,
):
    assert commit_agent(owner.name)

    agent = get_branch_model("agent", owner.name, "closure-agent")
    before = {
        trail.pk: branches_on(trail, owner.name).count()
        for trail in trail_closure(agent.target)
    }

    # same content, so the canon does not move
    assert not commit_agent(owner.name)

    after = {
        trail.pk: branches_on(trail, owner.name).count()
        for trail in trail_closure(agent.target)
    }

    assert after == before
    assert all(count == 1 for count in after.values())


def test_the_walk_goes_on_where_a_commit_stops(owner: IdentityModel):
    """
    A trail that has a branch is skipped, not stepped over: the walk carries
    on past it. So an owner left holding a tool group whose tools have no
    branches -- data from before this, or a branch someone deleted -- is
    repaired by the next commit that reaches them, even though the commit
    itself changes nothing.
    """
    assert commit_agent(owner.name)

    agent = get_branch_model("agent", owner.name, "closure-agent")
    tool_group = agent.target.tool_group
    tools = trail_closure(tool_group)

    assert len(tools) == 2

    for tool in tools:
        _ = branches_on(tool, owner.name).delete()

    assert not commit_agent(owner.name)

    assert branches_on(tool_group, owner.name).count() == 1

    for tool in tools:
        assert branches_on(tool, owner.name).count() == 1


def test_a_new_version_gives_the_new_parts_of_its_closure_branches(
    owner: IdentityModel,
):
    assert commit_agent(owner.name)
    assert commit_agent(owner.name, instructions="rewritten")

    assert dangling_trails(owner.name) == []


def test_the_closure_of_a_shared_model_belongs_to_the_owner(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    """
    A collaborator saving a shared model commits under its owner's name, so
    the closure is committed for the owner too -- and for nobody else.
    """
    assert commit_agent(other_owner.name)

    agent = get_branch_model("agent", other_owner.name, "closure-agent")

    assert dangling_trails(other_owner.name) == []

    for trail in trail_closure(agent.target):
        assert branches_on(trail, owner.name).count() == 0


def test_a_branch_made_for_the_closure_carries_nothing_beside_its_content(
    owner: IdentityModel,
):
    """
    Tags, collaborators and -- for a case -- expects belong to a version
    somebody saved deliberately. A closure branch is made on the owner's
    behalf by whoever saved the thing pointing at it, so it is given none of
    them, silently.
    """
    assert commit_agent(owner.name)

    agent = get_branch_model("agent", owner.name, "closure-agent")

    for trail in trail_closure(agent.target):
        made = branches_on(trail, owner.name).get()

        assert list(made.collaborators.all()) == []
        assert list(made.tags.all()) == []


def test_the_owner_s_own_branch_keeps_what_it_carries(owner: IdentityModel):
    """
    The other half of leaving an already-branched trail alone: a commit that
    reaches it does not strip the version the owner saved.
    """
    assert commit(
        trail=an_agent().connection,
        branch_details=BranchSchemaDetails(
            name="my connection",
            owner=owner.name,
            collaborators=["a collaborator"],
            tags=["tagged"],
        ),
    )

    assert commit_agent(owner.name)

    connection = get_branch_model("connection", owner.name, "my connection")

    assert [i.name for i in connection.collaborators.all()] == ["a collaborator"]
    assert [tag.name for tag in connection.tags.all()] == ["tagged"]


def test_an_expectation_gives_its_scorer_a_branch(owner: IdentityModel):
    """
    The guarantee is not the agent's: every entity with a closure gets it.
    """
    scorer = ScorerTrailSchema(command="a scorer nobody named")

    assert commit(
        trail=ExpectTrailSchema(payload="an expectation", scorer=scorer),
        branch_details=BranchSchemaDetails(name="an expectation", owner=owner.name),
    )

    expect = get_branch_model("expect", owner.name, "an expectation")
    scorer_trail = expect.target.scorer

    made = branches_on(scorer_trail, owner.name).get()

    assert made.name == resolve_branch_name("scorer", scorer_trail.fingerprint)


def test_the_test_inventory_leaves_nothing_branchless(
    inventory_fixture_commit: object,
    owner: IdentityModel,
):
    _ = inventory_fixture_commit

    assert dangling_trails(owner.name) == []


def test_the_closure_is_the_trails_and_only_the_trails(owner: IdentityModel):
    """
    `trail_closure` walks content. A tag hangs off the branch rather than
    the trail, so nothing but trails is ever reached, and the trail itself
    is not in its own closure.
    """
    _ = ensure_tag(owner, "agent", "a tag")

    assert commit_agent(owner.name)

    agent = get_branch_model("agent", owner.name, "closure-agent")
    closure = trail_closure(agent.target)

    assert all(isinstance(trail, TrailModel) for trail in closure)
    assert agent.target not in closure

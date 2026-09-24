from typing import Any

import pytest

from chatddx.core.models import IdentityModel
from chatddx.core.utils import ensure_tag
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.coercion.pydantic import CoercionTrailIn
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailIn
from chatddx.repo.entities.instruction.pydantic import InstructionTrailIn
from chatddx.repo.entities.machine.pydantic import MachineBranchDetails
from chatddx.repo.entities.output.pydantic import OutputTrailIn
from chatddx.repo.entities.reasoning.pydantic import ReasoningTrailIn
from chatddx.repo.entities.sampling.pydantic import SamplingTrailIn
from chatddx.repo.entities.tool.pydantic import ToolTrailIn
from chatddx.repo.entities.toolset.pydantic import ToolsetTrailIn
from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.repo.families.django import TrailModel
from chatddx.repo.families.pydantic import BranchDetails
from chatddx.repo.inventories import InventoryTrailIn
from chatddx.repo.names import closure_branch_name
from chatddx.repo.store.branch import (
    commit,
    get_branch_model,
    select_branch_models,
)
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

    for entity_name in ENTITY_NAMES:
        for branch_model in select_branch_models(entity_name, owner_name):
            for trail in trail_closure(branch_model.target):
                if not branches_on(trail, owner_name).exists():
                    dangling.append(trail)

    return dangling


def a_configuration(guidance: str = "nobody named the parts of this"):
    """
    A configuration whose whole closure is new and unnamed: five slices and a
    toolset of two tools.
    """
    return ConfigurationTrailIn(
        instruction=InstructionTrailIn(
            system="{{output_guidance}}",
            user="{{case}}",
            variables=["case", "output_guidance"],
        ),
        output=OutputTrailIn(guidance=guidance),
        coercion=CoercionTrailIn(mode="native"),
        reasoning=ReasoningTrailIn(effort="default"),
        sampling=SamplingTrailIn(defaults="model"),
        toolset=ToolsetTrailIn(
            tools=[
                ToolTrailIn(name="closure_tool_1"),
                ToolTrailIn(name="closure_tool_2"),
            ],
        ),
    )


def commit_configuration(
    owner_name: str, name: str = "closure-configuration", **kwargs: Any
) -> bool:
    return commit(
        trail=a_configuration(**kwargs),
        branch_details=BranchDetails(name=name, owner=owner_name),
    )


def test_a_commit_leaves_nothing_in_its_closure_branchless(owner: IdentityModel):
    assert commit_configuration(owner.name)

    configuration = get_branch_model(
        "configuration", owner.name, "closure-configuration"
    )
    closure = trail_closure(configuration.target)

    # instruction, output, coercion, reasoning, sampling, toolset, two tools
    assert len(closure) == 8

    for trail in closure:
        assert branches_on(trail, owner.name).count() == 1

    assert dangling_trails(owner.name) == []


def test_a_stack_s_closure_is_its_things(
    owner: IdentityModel,
    trails: InventoryTrailIn,
):
    """A container's stack reaches both systems, its own and its host's."""
    assert commit(
        trails.stack["qwen3-8b-awq@malborg"],
        BranchDetails(name="a stack", owner=owner.name),
    )

    stack = get_branch_model("stack", owner.name, "a stack")

    assert sorted(entity_of(trail).name for trail in trail_closure(stack.target)) == [
        "machine",
        "model",
        "os",
        "os",
        "serving",
    ]
    assert dangling_trails(owner.name) == []


def test_a_branch_made_for_the_closure_is_named_by_the_resolver(
    owner: IdentityModel,
):
    assert commit_configuration(owner.name)

    configuration = get_branch_model(
        "configuration", owner.name, "closure-configuration"
    )
    output = configuration.target.output

    made = branches_on(output, owner.name).get()

    assert made.name == closure_branch_name("output", output.fingerprint)
    assert made.name == f"output {output.fingerprint.rpartition(':')[2][:6]}"


def test_a_trail_the_owner_already_has_a_branch_on_is_left_alone(
    owner: IdentityModel,
):
    assert commit(
        trail=a_configuration().output,
        branch_details=BranchDetails(name="my output", owner=owner.name),
    )

    assert commit_configuration(owner.name)

    configuration = get_branch_model(
        "configuration", owner.name, "closure-configuration"
    )

    # the name they chose, and no second branch beside it
    assert [b.name for b in branches_on(configuration.target.output, owner.name)] == [
        "my output"
    ]


def test_committing_the_same_configuration_again_makes_no_further_branches(
    owner: IdentityModel,
):
    assert commit_configuration(owner.name)

    configuration = get_branch_model(
        "configuration", owner.name, "closure-configuration"
    )
    before = {
        trail.pk: branches_on(trail, owner.name).count()
        for trail in trail_closure(configuration.target)
    }

    # same content, so the head does not move
    assert not commit_configuration(owner.name)

    after = {
        trail.pk: branches_on(trail, owner.name).count()
        for trail in trail_closure(configuration.target)
    }

    assert after == before
    assert all(count == 1 for count in after.values())


def test_the_walk_goes_on_where_a_commit_stops(owner: IdentityModel):
    """
    A trail that has a branch is skipped, not stepped over: the walk carries
    on past it. So an owner left holding a toolset whose tools have no
    branches is repaired by the next commit that reaches them, even though
    the commit itself changes nothing.
    """
    assert commit_configuration(owner.name)

    configuration = get_branch_model(
        "configuration", owner.name, "closure-configuration"
    )
    toolset = configuration.target.toolset
    tools = trail_closure(toolset)

    assert len(tools) == 2

    for tool in tools:
        _ = branches_on(tool, owner.name).delete()

    assert not commit_configuration(owner.name)

    assert branches_on(toolset, owner.name).count() == 1

    for tool in tools:
        assert branches_on(tool, owner.name).count() == 1


def test_a_new_version_gives_the_new_parts_of_its_closure_branches(
    owner: IdentityModel,
):
    assert commit_configuration(owner.name)
    assert commit_configuration(owner.name, guidance="rewritten")

    assert dangling_trails(owner.name) == []


def test_the_closure_of_a_shared_configuration_belongs_to_the_owner(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    """
    A collaborator saving a shared configuration commits under its owner's
    name, so the closure is committed for the owner too -- and for nobody
    else.
    """
    assert commit_configuration(other_owner.name)

    configuration = get_branch_model(
        "configuration", other_owner.name, "closure-configuration"
    )

    assert dangling_trails(other_owner.name) == []

    for trail in trail_closure(configuration.target):
        assert branches_on(trail, owner.name).count() == 0


def test_a_branch_made_for_the_closure_carries_nothing_beside_its_content(
    owner: IdentityModel,
    trails: InventoryTrailIn,
):
    assert commit(
        trails.stack["qwen3-8b-awq@pelle"],
        BranchDetails(name="a stack", owner=owner.name),
    )

    stack = get_branch_model("stack", owner.name, "a stack")

    for trail in trail_closure(stack.target):
        made = branches_on(trail, owner.name).get()

        assert list(made.collaborators.all()) == []
        assert list(made.tags.all()) == []

    # a machine's details, all at their defaults
    machine = branches_on(stack.target.machine, owner.name).get()

    assert machine.details == {"unreliable": False, "specs": None}


def test_the_owner_s_own_branch_keeps_what_it_carries(
    owner: IdentityModel,
    trails: InventoryTrailIn,
):
    """
    The other half of leaving an already-branched trail alone: a commit that
    reaches it does not strip the version the owner saved, details included.
    """
    stack = trails.stack["qwen3-8b-awq@pelle"]

    assert commit(
        trail=stack.machine,
        branch_details=MachineBranchDetails(
            name="my machine",
            owner=owner.name,
            unreliable=True,
            collaborators=["a collaborator"],
            tags=["tagged"],
        ),
    )

    assert commit(stack, BranchDetails(name="a stack", owner=owner.name))

    machine = get_branch_model("machine", owner.name, "my machine")

    assert [i.name for i in machine.collaborators.all()] == ["a collaborator"]
    assert [tag.name for tag in machine.tags.all()] == ["tagged"]
    assert machine.details["unreliable"] is True


def test_the_test_inventory_leaves_nothing_branchless(
    inventory_fixture_commit: object,
    owner: IdentityModel,
):
    _ = inventory_fixture_commit

    assert dangling_trails(owner.name) == []


def test_committed_in_order_every_part_keeps_the_name_its_record_gave_it(
    inventory_fixture_commit: object,
    owner: IdentityModel,
):
    """
    Committed in the order `EntityName` gives, every trail a composition
    reaches already has its own branch, and the closure makes none.
    """
    _ = inventory_fixture_commit

    for entity_name in ENTITY_NAMES:
        for branch in select_branch_models(entity_name, owner.name):
            assert not branch.name.startswith(f"{entity_name} "), branch.name


def test_the_closure_is_the_trails_and_only_the_trails(owner: IdentityModel):
    """
    `trail_closure` walks content. A tag hangs off the branch rather than
    the trail, so nothing but trails is ever reached, and the trail itself
    is not in its own closure.
    """
    _ = ensure_tag(owner, "configuration", "a tag")

    assert commit_configuration(owner.name)

    configuration = get_branch_model(
        "configuration", owner.name, "closure-configuration"
    )
    closure = trail_closure(configuration.target)

    assert all(isinstance(trail, TrailModel) for trail in closure)
    assert configuration.target not in closure

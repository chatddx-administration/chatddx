"""
A branch is an owner's named version of a trail, and the details beside it.

What a version is: its trail and its details. Resolution reads details, a
model's facts and a stack's endpoint, and a trial must be able to say which
version it resolved against, so a change to them is a new version
(new-datamodel.md §1). What a branch is related to, tags and collaborators,
changes in place.
"""

from typing import Any, cast

import pytest
from pydantic import ValidationError

from chatddx.core.models import IdentityModel, TagModel
from chatddx.core.utils import ensure_tag
from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.case.pydantic import CaseTrailIn
from chatddx.repo.entities.machine.pydantic import (
    MachineBranchDetails,
    MachineBranchOut,
    MachineTrailIn,
)
from chatddx.repo.entities.model.pydantic import ModelBranchDetails, ModelBranchOut
from chatddx.repo.entities.stack.pydantic import StackBranchDetails
from chatddx.repo.entities.tool.django import ToolBranchModel
from chatddx.repo.entities.tool.pydantic import ToolBranchDetails
from chatddx.repo.entities.toolset.django import ToolsetTrailModel
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.pydantic import BranchDetails
from chatddx.repo.inventories import InventoryTrailIn
from chatddx.repo.names import short_fingerprint
from chatddx.repo.store.branch import (
    AmbiguousBranchError,
    BranchNotFoundError,
    commit,
    commit_copies,
    get_branch_model,
    get_branch_out,
    get_shared_branch_model,
    get_visible_branch_model,
    select_visible_branch_models,
)
from chatddx.repo.store.trail import dump_trail

pytestmark = pytest.mark.django_db(transaction=True)

MACHINE = MachineTrailIn(machine_id="00000000-0000-4000-8000-000000000001")  # pyright: ignore[reportArgumentType]


def versions(entity: EntityName, owner: IdentityModel, name: str) -> list[Any]:
    return list(
        entity_of(entity)
        .branch_model.objects.filter(owner=owner, name=name)
        .order_by("timestamp", "id")
    )


def machine_details(owner: IdentityModel, **details: Any) -> MachineBranchDetails:
    return MachineBranchDetails(name="box", owner=owner.name, **details)


def test_a_commit_makes_a_version_the_head(owner: IdentityModel):
    assert commit(MACHINE, machine_details(owner, unreliable=True))

    spec = cast(MachineBranchOut, get_branch_out("machine", owner.name, "box"))

    assert spec.target.fingerprint == MACHINE.fingerprint
    assert spec.details.unreliable is True


def test_details_are_kept_beside_the_trail_as_json(owner: IdentityModel):
    assert commit(
        MACHINE,
        machine_details(owner, specs={"cpu": "a CPU", "ram_gib": 32}),
    )

    branch = get_branch_model("machine", owner.name, "box")

    assert branch.details == {
        "unreliable": False,
        "specs": {"gpus": [], "cpu": "a CPU", "ram_gib": 32, "location": None},
    }


def test_committing_the_same_version_again_changes_nothing(owner: IdentityModel):
    assert commit(MACHINE, machine_details(owner, unreliable=True))
    assert not commit(MACHINE, machine_details(owner, unreliable=True))

    assert len(versions("machine", owner, "box")) == 1


def test_a_change_to_details_is_a_new_version(
    owner: IdentityModel,
    trails: InventoryTrailIn,
):
    """
    The trail stays put, since details aren't content; the branch gets a
    version whose facts a trial can name.
    """
    model = trails.model["gpt-oss-20b"]

    assert commit(model, ModelBranchDetails(name="gpt-oss-20b", owner=owner.name))

    assert commit(
        model,
        ModelBranchDetails.model_validate(
            {
                "name": "gpt-oss-20b",
                "owner": owner.name,
                "facts": {"reasoning": {"off": {"refused": "always reasons"}}},
            }
        ),
    )

    first, second = versions("model", owner, "gpt-oss-20b")

    assert first.target_id == second.target_id
    assert first.details["facts"]["reasoning"]["off"] is None
    assert second.details["facts"]["reasoning"]["off"] == {"refused": "always reasons"}

    head = cast(ModelBranchOut, get_branch_out("model", owner.name, "gpt-oss-20b"))

    assert head.details.facts.reasoning.resolve("off") == (
        "off",
        head.details.facts.reasoning.off,
    )


def test_a_change_to_what_a_branch_is_related_to_is_not_a_new_version(
    owner: IdentityModel,
):
    assert commit(MACHINE, machine_details(owner, tags=["a"]))
    assert not commit(MACHINE, machine_details(owner, tags=["b"], collaborators=["c"]))

    (branch,) = versions("machine", owner, "box")

    assert [tag.name for tag in branch.tags.all()] == ["b"]
    assert [identity.name for identity in branch.collaborators.all()] == ["c"]


def test_a_new_version_carries_over_the_relations_it_doesn_t_name(
    owner: IdentityModel,
):
    assert commit(MACHINE, machine_details(owner, tags=["a"]))
    assert commit(MACHINE, machine_details(owner, unreliable=True))

    first, second = versions("machine", owner, "box")

    assert [tag.name for tag in second.tags.all()] == ["a"]
    assert [tag.name for tag in first.tags.all()] == ["a"]


def test_a_version_carries_the_details_it_is_given_and_no_others(
    owner: IdentityModel,
):
    """
    Details aren't relations: a version says all of them, and one given none
    has none, whatever the version before it said.
    """
    assert commit(MACHINE, machine_details(owner, specs={"cpu": "a CPU"}))
    assert commit(MACHINE, machine_details(owner))

    branch = get_branch_model("machine", owner.name, "box")

    assert branch.details == {"unreliable": False, "specs": None}


def test_details_are_the_owner_s(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    """One machine, one trail row, and what each owner says of it."""
    assert commit(MACHINE, machine_details(owner, specs={"location": "here"}))
    assert commit(
        MACHINE,
        MachineBranchDetails(
            name="box",
            owner=other_owner.name,
            specs={"location": "there"},  # pyright: ignore[reportArgumentType]
        ),
    )

    mine = get_branch_model("machine", owner.name, "box")
    theirs = get_branch_model("machine", other_owner.name, "box")

    assert mine.target_id == theirs.target_id
    assert mine.details["specs"]["location"] == "here"
    assert theirs.details["specs"]["location"] == "there"


def test_a_caller_that_says_nothing_of_details_gets_the_defaults(
    owner: IdentityModel,
):
    assert commit(MACHINE, BranchDetails(name="box", owner=owner.name))

    assert get_branch_model("machine", owner.name, "box").details == {
        "unreliable": False,
        "specs": None,
    }


def test_a_detail_the_entity_doesn_t_carry_is_refused(owner: IdentityModel):
    """A machine has no endpoint: saying it has one is wrong, not generous."""
    with pytest.raises(ValidationError, match="endpoint"):
        _ = commit(
            MACHINE,
            StackBranchDetails(
                name="box",
                owner=owner.name,
                endpoint="http://box:8000/v1",  # pyright: ignore[reportArgumentType]
            ),
        )


def test_a_tag_belongs_to_one_owner_and_one_entity(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    machine_tag = ensure_tag(owner, "machine", "clinical")

    for identity in (owner, other_owner):
        assert commit(
            CaseTrailIn(payload="case payload"),
            BranchDetails(name="case-1", owner=identity.name, tags=["clinical"]),
        )

    tags = TagModel.objects.filter(name="clinical")

    assert {(tag.owner.name, tag.entity) for tag in tags} == {
        (owner.name, "machine"),
        (owner.name, "case"),
        (other_owner.name, "case"),
    }
    assert machine_tag in tags


def test_two_owners_of_one_case_share_its_trail(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    for identity in (owner, other_owner):
        assert commit(
            CaseTrailIn(payload="case payload"),
            BranchDetails(name="case-1", owner=identity.name),
        )

    mine = get_branch_model("case", owner.name, "case-1")
    theirs = get_branch_model("case", other_owner.name, "case-1")

    assert mine.target_id == theirs.target_id
    assert mine.pk != theirs.pk


def case(name: str, owner: str, *collaborators: str, payload: str = "") -> None:
    assert commit(
        CaseTrailIn(payload=payload or f"{owner}'s {name}"),
        BranchDetails(name=name, owner=owner, collaborators=list(collaborators)),
    )


def test_an_identity_sees_its_own_branches_and_those_shared_with_it(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    case("mine", owner.name)
    case("shared", other_owner.name, owner.name)
    case("theirs", other_owner.name)

    visible = select_visible_branch_models("case", owner.name)

    assert [(m.name, m.owner.name) for m in visible] == [
        ("mine", "alex"),
        ("shared", "other"),
    ]


def test_its_own_branch_shadows_a_shared_one_of_the_same_name(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    case("case-1", other_owner.name, owner.name)
    case("case-1", owner.name)

    visible = select_visible_branch_models("case", owner.name)
    found = get_visible_branch_model("case", owner.name, "case-1")

    assert [m.owner.name for m in visible] == ["alex"]
    assert found.owner.name == "alex"


def test_a_shared_branch_is_found_by_its_name_or_by_its_trail(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    case("case-1", other_owner.name, owner.name)

    by_name = get_visible_branch_model("case", owner.name, "case-1")
    by_trail = get_visible_branch_model("case", owner.name, trail=by_name.target_id)

    assert by_name.owner.name == "other"
    assert by_trail.pk == by_name.pk


def test_a_branch_not_shared_with_an_identity_isn_t_found(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    case("case-1", other_owner.name)

    with pytest.raises(BranchNotFoundError, match="no case 'case-1' for alex"):
        _ = get_visible_branch_model("case", owner.name, "case-1")


def test_one_name_shared_by_two_is_ambiguous(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    case("case-1", other_owner.name, owner.name)
    case("case-1", "third", owner.name)

    with pytest.raises(AmbiguousBranchError, match="other, third"):
        _ = get_visible_branch_model("case", owner.name, "case-1")


def test_shared_by_one_owner_alone_nothing_is_ambiguous(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    case("case-1", other_owner.name, owner.name)
    case("case-1", "third", owner.name)
    case("case-2", "third", owner.name)

    found = get_visible_branch_model("case", owner.name, "case-1", shared_by="other")
    visible = select_visible_branch_models("case", owner.name, shared_by="other")

    assert found.owner.name == "other"
    assert [(m.name, m.owner.name) for m in visible] == [("case-1", "other")]

    with pytest.raises(BranchNotFoundError):
        _ = get_visible_branch_model("case", owner.name, "case-2", shared_by="other")


def test_shared_by_one_owner_its_own_still_shadows(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    case("case-1", other_owner.name, owner.name)
    case("case-1", owner.name)

    found = get_visible_branch_model("case", owner.name, "case-1", shared_by="other")

    assert found.owner.name == "alex"


def test_an_owner_s_branch_is_found_by_the_owner_where_it_is_shared(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    case("case-1", other_owner.name, owner.name)
    case("case-1", owner.name)

    theirs = get_shared_branch_model("case", owner.name, other_owner.name, "case-1")
    mine = get_shared_branch_model("case", owner.name, owner.name, "case-1")

    assert theirs.owner.name == "other"
    assert mine.owner.name == "alex"


def test_an_owner_s_branch_not_shared_isn_t_found_by_the_owner(
    owner: IdentityModel,
    other_owner: IdentityModel,
):
    case("case-1", other_owner.name)

    with pytest.raises(BranchNotFoundError, match="no case 'other/case-1' for alex"):
        _ = get_shared_branch_model("case", owner.name, other_owner.name, "case-1")


SENTINEL = {
    "sentinel_string": "chatddx.runtime.tools.sentinel_string:sentinel_string",
    "sentinel_op": "chatddx.runtime.tools.sentinel_op:sentinel_op",
}


def sentinel_tools(owner: str, trails: InventoryTrailIn) -> None:
    """The sentinel toolset's tools as `owner`'s, each with what it runs."""
    for name, entry_point in SENTINEL.items():
        assert commit(
            trails.tool[name],
            ToolBranchDetails.model_validate(
                {
                    "name": name,
                    "owner": owner,
                    "implementation": {"entry_point": entry_point},
                }
            ),
        )


def tool_names(owner: IdentityModel) -> list[str]:
    return sorted(branch.name for branch in ToolBranchModel.objects.filter(owner=owner))


def test_a_copy_is_the_source_s_branch_under_its_name_with_its_details(
    owner: IdentityModel,
    other_owner: IdentityModel,
    trails: InventoryTrailIn,
):
    sentinel_tools(other_owner.name, trails)
    toolset = dump_trail(ToolsetTrailModel, trails.toolset["sentinel"])

    copied = commit_copies(toolset, owner.name, other_owner.name)

    assert sorted(copied) == ["tool sentinel_op", "tool sentinel_string"]

    for name, entry_point in SENTINEL.items():
        mine = get_branch_model("tool", owner.name, name)
        assert mine.details["implementation"]["entry_point"] == entry_point

    assert commit(toolset, BranchDetails(name="mine", owner=owner.name))
    assert tool_names(owner) == ["sentinel_op", "sentinel_string"]


def test_what_the_owner_has_or_has_named_otherwise_is_not_copied(
    owner: IdentityModel,
    other_owner: IdentityModel,
    trails: InventoryTrailIn,
):
    sentinel_tools(other_owner.name, trails)
    assert commit(
        trails.tool["sentinel_op"], BranchDetails(name="my-op", owner=owner.name)
    )
    assert commit(
        trails.tool["web_search"],
        BranchDetails(name="sentinel_string", owner=owner.name),
    )
    toolset = dump_trail(ToolsetTrailModel, trails.toolset["sentinel"])

    assert commit_copies(toolset, owner.name, other_owner.name) == []

    assert commit(toolset, BranchDetails(name="mine", owner=owner.name))
    fingerprint = trails.tool["sentinel_string"].fingerprint
    assert tool_names(owner) == sorted(
        ["my-op", "sentinel_string", f"tool {short_fingerprint(fingerprint)}"]
    )

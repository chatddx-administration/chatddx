from typing import Any

import pytest

from chatddx.core.models import IdentityModel
from chatddx.repo.entities.coercion.pydantic import CoercionTrailIn
from chatddx.repo.entities.configuration.django import (
    ConfigurationBranchModel,
    ConfigurationTrailModel,
)
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailIn
from chatddx.repo.entities.instruction.pydantic import InstructionTrailIn
from chatddx.repo.entities.llm.django import LLMTrailModel
from chatddx.repo.entities.machine.pydantic import (
    MachineBranchDetails,
    MachineBranchOut,
    MachineTrailIn,
)
from chatddx.repo.entities.output.django import OutputTrailModel
from chatddx.repo.entities.output.pydantic import OutputTrailIn
from chatddx.repo.entities.reasoning.django import ReasoningTrailModel
from chatddx.repo.entities.reasoning.pydantic import ReasoningTrailIn
from chatddx.repo.entities.sampling.pydantic import SamplingTrailIn
from chatddx.repo.entities.stack.django import StackTrailModel
from chatddx.repo.entities.tool.django import ToolTrailModel
from chatddx.repo.entities.tool.pydantic import ToolTrailIn
from chatddx.repo.entities.toolset.pydantic import ToolsetTrailIn
from chatddx.repo.families.pydantic import BranchDetails
from chatddx.repo.names import short_fingerprint
from chatddx.repo.queries import reaching
from chatddx.repo.store.branch import (
    branch_named,
    commit,
    get_branch_model,
    holders_of,
    name_of,
    readable,
)
from chatddx.repo.store.timeline import alike, saving, select_versions
from chatddx.repo.store.trail import dump_trail
from chatddx.repo.utils import Reach, reaches

pytestmark = pytest.mark.django_db

FIRST = MachineTrailIn(machine_id="00000000-0000-4000-8000-000000000001")  # pyright: ignore[reportArgumentType]
SECOND = MachineTrailIn(machine_id="00000000-0000-4000-8000-000000000002")  # pyright: ignore[reportArgumentType]


def boxed(
    owner: IdentityModel,
    trail: MachineTrailIn = FIRST,
    name: str = "box",
    **details: Any,
) -> bool:
    return commit(trail, MachineBranchDetails(name=name, owner=owner.name, **details))


def a_configuration(*tools: str) -> ConfigurationTrailIn:
    return ConfigurationTrailIn(
        instruction=InstructionTrailIn(
            system="{{output_guidance}}",
            user="{{case}}",
            variables=["case", "output_guidance"],
        ),
        output=OutputTrailIn(guidance="nobody named the parts of this"),
        coercion=CoercionTrailIn(mode="native"),
        reasoning=ReasoningTrailIn(effort="default"),
        sampling=SamplingTrailIn(defaults="generation_config"),
        toolset=ToolsetTrailIn(tools=[ToolTrailIn(name=tool) for tool in tools]),
    )


def test_a_timeline_s_versions_come_oldest_first(owner: IdentityModel):
    assert boxed(owner, FIRST, unreliable=True)
    assert boxed(owner, SECOND)
    assert boxed(owner, SECOND, name="crate")

    versions = select_versions("machine", owner.name, "box")

    assert [version.trail.fingerprint for version in versions] == [
        FIRST.fingerprint,
        SECOND.fingerprint,
    ]
    assert [version.details["unreliable"] for version in versions] == [True, False]
    assert select_versions("machine", owner.name, "nowhere") == []


def test_another_is_shown_the_versions_shared_with_them(
    owner: IdentityModel, other_owner: IdentityModel
):
    assert boxed(owner, FIRST)
    assert boxed(owner, SECOND, collaborators=[other_owner.name])

    theirs = select_versions("machine", owner.name, "box", other_owner.name)

    assert [version.trail.fingerprint for version in theirs] == [SECOND.fingerprint]
    assert len(select_versions("machine", owner.name, "box", owner.name)) == 2
    assert select_versions("machine", owner.name, "box", "nobody") == []


def test_saving_says_what_a_name_will_come_to(owner: IdentityModel):
    fresh = saving("machine", owner.name, "box")

    assert (fresh.head, fresh.versions, fresh.version, fresh.unchanged) == (
        None,
        0,
        1,
        False,
    )
    assert not fresh.deleted

    assert boxed(owner, FIRST)

    again = saving("machine", owner.name, "box", FIRST.fingerprint)

    assert again.head is not None
    assert again.head.trail.fingerprint == FIRST.fingerprint
    assert (again.versions, again.version, again.unchanged) == (1, 2, True)
    assert not saving("machine", owner.name, "box", SECOND.fingerprint).unchanged


def test_names_alike_are_the_owner_s_other_spellings(owner: IdentityModel):
    assert boxed(owner, name="box")
    assert boxed(owner, name="Box")
    assert boxed(owner, name="BOX")

    assert alike("machine", owner.name, "box") == ["BOX", "Box"]
    assert alike("machine", owner.name, "crate") == []


def test_a_row_is_readable_to_its_owner_and_whoever_its_timeline_is_shared_with(
    owner: IdentityModel, other_owner: IdentityModel
):
    assert boxed(owner, FIRST)
    first = get_branch_model("machine", owner.name, "box")

    assert readable(first, owner.name)
    assert not readable(first, other_owner.name)

    assert boxed(owner, SECOND, collaborators=[other_owner.name])

    assert readable(first, other_owner.name)


def test_a_trail_goes_by_its_branch_s_name_or_its_fingerprint(
    owner: IdentityModel, other_owner: IdentityModel
):
    assert boxed(owner, FIRST)
    model = get_branch_model("machine", owner.name, "box")
    out = MachineBranchOut.model_validate(model).trail

    assert branch_named("machine", owner.name, model.trail) == "box"
    assert branch_named("machine", owner.name, model.trail_id) == "box"
    assert branch_named("machine", other_owner.name, out) is None
    assert name_of("machine", owner.name, out) == "box"
    assert name_of("machine", other_owner.name, model.trail) == short_fingerprint(
        FIRST.fingerprint
    )


def test_the_holders_of_a_fingerprint_are_the_visible_branches_holding_it(
    owner: IdentityModel, other_owner: IdentityModel
):
    assert boxed(owner, FIRST, name="box")
    assert boxed(owner, FIRST, name="crate")
    assert boxed(owner, SECOND, name="chest")
    assert boxed(other_owner, FIRST, name="theirs")

    assert sorted(
        held.name for held in holders_of("machine", owner.name, FIRST.fingerprint)
    ) == ["box", "crate"]
    assert [
        held.name for held in holders_of("machine", other_owner.name, FIRST.fingerprint)
    ] == ["theirs"]
    assert holders_of("machine", owner.name, "cddx-trail/1:sha256:0") == []


def test_reaches_walks_relations_and_arrays_down_to_a_trail():
    assert reaches(ConfigurationTrailModel, ReasoningTrailModel) == [Reach("reasoning")]
    assert reaches(ConfigurationTrailModel, ToolTrailModel) == [
        Reach("toolset__tools", array=True)
    ]
    assert reaches(StackTrailModel, LLMTrailModel) == [Reach("llm")]
    assert reaches(StackTrailModel, ToolTrailModel) == []
    assert (Reach("reasoning").lookup, Reach("toolset__tools", array=True).lookup) == (
        "reasoning__in",
        "toolset__tools__overlap",
    )


def test_reaching_finds_what_holds_a_trail_directly_or_in_an_array(
    owner: IdentityModel,
):
    with_first = dump_trail(ConfigurationTrailModel, a_configuration("first", "second"))
    without = dump_trail(ConfigurationTrailModel, a_configuration("third"))
    first = ToolTrailModel.objects.get(name="first")
    assert commit(
        a_configuration("first", "second"), BranchDetails(name="held", owner=owner.name)
    )
    assert commit(
        a_configuration("third"), BranchDetails(name="free", owner=owner.name)
    )

    holding = reaching(ConfigurationTrailModel, ToolTrailModel, [first.pk])
    none = reaching(ConfigurationTrailModel, ToolTrailModel, [])
    through = reaching(ConfigurationTrailModel, ToolTrailModel, [first.pk], "trail")
    output = reaching(ConfigurationTrailModel, OutputTrailModel, [with_first.output_id])

    assert list(ConfigurationTrailModel.objects.filter(holding)) == [with_first]
    assert not ConfigurationTrailModel.objects.filter(none).exists()
    assert [
        branch.name for branch in ConfigurationBranchModel.objects.filter(through)
    ] == ["held"]
    assert set(ConfigurationTrailModel.objects.filter(output)) == {with_first, without}

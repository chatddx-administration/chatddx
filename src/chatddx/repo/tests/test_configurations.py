import pytest

from chatddx.core.models import IdentityModel
from chatddx.repo.bundles import entity_of
from chatddx.repo.queries import qs_head
from chatddx.repo.store.configuration import (
    get_configuration_async,
    select_configurations_async,
)

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.django_db(transaction=True),
]


async def test_a_configuration_is_one_variation_of_each_slice(
    inventory_fixture_commit: object,
    owner: IdentityModel,
):
    _ = inventory_fixture_commit

    plan = await get_configuration_async(owner.name, "plan-web")

    assert plan.trail.instruction.variables == [
        "case",
        "output_guidance",
        "schema_prompt",
        "tool_guidance",
    ]
    assert plan.trail.output.views == {
        "differential": "$.diagnoses[*].diagnosis",
        "warning": "$.acute_warning",
        "disposition": "$.management.disposition",
        "critical": "$.diagnoses[?(@.critical)].diagnosis",
    }
    assert plan.trail.coercion.mode == "native"
    assert plan.trail.reasoning.effort == "default"
    assert plan.trail.sampling.defaults == "recommended"
    assert plan.trail.toolset is not None
    assert [tool.name for tool in plan.trail.toolset.tools] == ["web_search"]
    assert plan.tags == ["ddx"]


async def test_configurations_are_selected_by_what_they_name(
    inventory_fixture_commit: object,
    owner: IdentityModel,
):
    _ = inventory_fixture_commit

    qs = qs_head(entity_of("configuration").branch_model.objects.all(), owner.name)

    free_text = await select_configurations_async(
        owner_name=owner.name,
        qs=qs.filter(trail__output__answer_schema__isnull=True),
    )
    with_tools = await select_configurations_async(
        owner_name=owner.name,
        qs=qs.filter(trail__toolset__isnull=False),
    )

    assert sorted(c.name for c in free_text) == [
        "baseline",
        "free-text",
        "test-tools",
    ]
    assert sorted(c.name for c in with_tools) == ["plan-web", "test-tools"]

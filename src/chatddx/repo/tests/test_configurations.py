import pytest

from chatddx.core.models import IdentityModel
from chatddx.repo.bundles import entity_of
from chatddx.repo.queries import qs_canon
from chatddx.repo.shufflers.configuration import (
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

    assert plan.target.instruction.variables == [
        "case",
        "output_guidance",
        "schema_prompt",
        "tool_guidance",
    ]
    assert plan.target.output.views == {
        "differential": "$.diagnoses[*].diagnosis",
        "warning": "$.acute_warning",
        "disposition": "$.management.disposition",
    }
    assert plan.target.coercion.mode == "native"
    assert plan.target.reasoning.effort == "default"
    assert plan.target.sampling.defaults == "recommended"
    assert plan.target.toolset is not None
    assert [tool.name for tool in plan.target.toolset.tools] == ["web_search"]
    assert plan.tags == ["ddx"]


async def test_configurations_are_selected_by_what_they_name(
    inventory_fixture_commit: object,
    owner: IdentityModel,
):
    _ = inventory_fixture_commit

    qs = qs_canon(entity_of("configuration").branch_model.objects.all(), owner.name)

    free_text = await select_configurations_async(
        owner_name=owner.name,
        qs=qs.filter(target__output__schema__isnull=True),
    )
    with_tools = await select_configurations_async(
        owner_name=owner.name,
        qs=qs.filter(target__toolset__isnull=False),
    )

    assert sorted(c.name for c in free_text) == [
        "baseline",
        "free-text",
        "test-tools",
    ]
    assert sorted(c.name for c in with_tools) == ["plan-web", "test-tools"]

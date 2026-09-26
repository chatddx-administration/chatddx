import pytest

from chatddx.core import settings
from chatddx.repo.bundles import entity_of
from chatddx.repo.queries import qs_head
from chatddx.repo.store.configuration import get_configuration, select_configurations

# the archive, as the session's seed committed the test inventory
pytestmark = pytest.mark.django_db

ARCHIVE = settings.ARCHIVE_IDENTITY_NAME


def test_a_configuration_is_one_variation_of_each_slice():
    plan = get_configuration(ARCHIVE, "plan-web")

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


def test_configurations_are_selected_by_what_they_name():
    qs = qs_head(entity_of("configuration").branch_model.objects.all(), ARCHIVE)

    free_text = select_configurations(
        owner_name=ARCHIVE, qs=qs.filter(trail__output__answer_schema__isnull=True)
    )
    with_tools = select_configurations(
        owner_name=ARCHIVE, qs=qs.filter(trail__toolset__isnull=False)
    )

    assert sorted(c.name for c in free_text) == [
        "baseline",
        "free-text",
        "test-tools",
    ]
    assert sorted(c.name for c in with_tools) == ["plan-web", "test-tools"]

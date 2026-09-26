import pytest

from chatddx.core import settings
from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.repo.inventories import InventoryBranchOut, InventoryTrailIn
from chatddx.repo.store.inventory import form_data_out, owned_inventory

pytestmark = pytest.mark.django_db

COUNTS = {
    "machine": 3,
    "os": 3,
    "llm": 2,
    "serving": 5,
    "client": 2,
    "stack": 5,
    "tool": 3,
    "toolset": 2,
    "instruction": 3,
    "output": 5,
    "coercion": 5,
    "reasoning": 9,
    "sampling": 5,
    "configuration": 12,
    "case": 2,
    "scorer": 4,
}


def test_trail_schema(trails: InventoryTrailIn):
    assert {e: len(getattr(trails, e)) for e in ENTITY_NAMES} == COUNTS


def test_a_committed_inventory_reads_back_as_models_specs_and_form_data():
    # the archive, as the session's seed committed the test inventory
    models = owned_inventory(settings.ARCHIVE_IDENTITY_NAME)
    specs = InventoryBranchOut.model_validate(models)
    form_data = form_data_out(specs)

    assert {e: len(models[e]) for e in ENTITY_NAMES} == COUNTS
    assert {e: len(getattr(specs, e)) for e in ENTITY_NAMES} == COUNTS

    stack = specs.stack["qwen3-8b-awq@malborg"]

    assert stack.details.served_name == "Qwen/Qwen3-8B-AWQ"
    assert stack.trail.host_os is not None
    assert stack.tags == ["rtx-5090"]
    assert {e: len(getattr(form_data, e)) for e in ENTITY_NAMES} == COUNTS

    tool = form_data.tool["web_search"]

    assert (tool.name, tool.tool_name) == ("web_search", "web_search")
    assert form_data.stack["qwen3-8b-awq@pelle"].endpoint == (
        "http://pelle.km:12009/v1/"
    )

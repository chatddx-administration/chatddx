"""
A trail is content, content-addressed and immutable: what goes into the
database is what comes back, down to the order of a schema's keys, and a
trail row is never written twice.
"""

from typing import Any, cast

import pytest
from django.db import ProgrammingError, transaction

from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.output.django import OutputTrailModel
from chatddx.repo.entities.stack.django import StackTrailModel
from chatddx.repo.entities.toolset.pydantic import ToolsetTrailSpec
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.pydantic import TrailSchema, TrailSpec
from chatddx.repo.inventories import InventoryTrailSchema
from chatddx.repo.shufflers.trail import dump_trail, load_trail


def records(trails: InventoryTrailSchema) -> list[tuple[EntityName, str, TrailSchema]]:
    return [
        (cast(EntityName, entity), name, trail)
        for entity, table in trails
        for name, trail in cast(dict[str, TrailSchema], table).items()
    ]


pytestmark = pytest.mark.django_db


def test_every_field_of_a_trail_is_fingerprinted_and_nothing_else(
    trails: InventoryTrailSchema,
):
    """A field is fingerprinted if and only if it is trail content (§1)."""
    for entity, name, trail in records(trails):
        fields = set(entity_of(entity).trail_schema.model_fields)

        assert set(trail.canonical_input()) == fields, f"{entity} {name}"


def test_every_trail_of_the_inventory_comes_back_as_it_went_in(
    trails: InventoryTrailSchema,
):
    """
    Loaded back and validated as content again, each trail has the
    fingerprint it went in with: nothing it holds was lost, reordered or
    rounded on the way.
    """
    for entity, name, trail in records(trails):
        bundle = entity_of(entity)

        _ = dump_trail(bundle.trail_model, trail)
        spec = cast(TrailSpec, load_trail(entity, trail.fingerprint, bundle.trail_spec))

        again = bundle.trail_schema.model_validate(spec.model_dump())

        assert spec.fingerprint == trail.fingerprint, f"{entity} {name}"
        assert again.fingerprint == trail.fingerprint, f"{entity} {name}"


def test_a_schema_keeps_its_order_in_the_database(trails: InventoryTrailSchema):
    """jsonb would sort `properties` by length, then by bytes."""
    output = trails.output["management-plan"]
    stored = dump_trail(OutputTrailModel, output)

    fetched = OutputTrailModel.objects.get(pk=stored.pk)
    # an OrderedJSONField reads back as the document, whatever TextField says
    schema = cast(dict[str, Any], cast(object, fetched.schema))

    assert list(schema["properties"]) == [
        "acute_warning",
        "diagnoses",
        "management",
        "sources",
    ]


def test_the_same_content_is_one_row(trails: InventoryTrailSchema):
    stack = trails.stack["qwen3-8b-awq@pelle"]
    model = entity_of("stack").trail_model

    first = dump_trail(model, stack)
    second = dump_trail(model, stack.model_copy(deep=True))

    assert first.pk == second.pk
    assert model.objects.count() == 1


def test_a_trail_s_parts_are_shared_by_whatever_reaches_them(
    trails: InventoryTrailSchema,
):
    pelle = dump_trail(StackTrailModel, trails.stack["qwen3-8b-awq@pelle"])
    malborg = dump_trail(StackTrailModel, trails.stack["qwen3-8b-awq@malborg"])

    assert pelle.model_id == malborg.model_id
    assert pelle.host_os_id is None
    assert malborg.host_os_id is not None


def test_a_toolset_keeps_the_order_of_its_tools(trails: InventoryTrailSchema):
    toolset = trails.toolset["sentinel"]
    bundle = entity_of("toolset")

    _ = dump_trail(bundle.trail_model, toolset)
    spec = cast(
        ToolsetTrailSpec,
        load_trail("toolset", toolset.fingerprint, bundle.trail_spec),
    )

    assert [tool.name for tool in spec.tools] == ["sentinel_string", "sentinel_op"]


@pytest.mark.parametrize("change", ["save", "delete"])
def test_a_trail_is_immutable(trails: InventoryTrailSchema, change: str):
    stored = dump_trail(
        entity_of("configuration").trail_model, trails.configuration["plan"]
    )

    with pytest.raises(ProgrammingError, match="immutable"), transaction.atomic():
        getattr(stored, change)()

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from django.db import ProgrammingError

from chatddx.repo.bundles import entity_of
from chatddx.repo.entities.agent.django import AgentTrailModel
from chatddx.repo.inventories import InventoryTrailSchema
from chatddx.repo.registry import EntityName
from chatddx.repo.shufflers.trail import dump_trail_async, load_trail_async
from chatddx.repo.tests import identity_boundary

schemas: tuple[tuple[EntityName, str], ...] = (
    ("connection", "connection-1"),
    ("sampling_params", "sampling_params-1"),
    ("tool_group", "tool_group-1"),
    ("tool", "tool-1"),
    ("output_type", "output_type-1"),
    ("agent", "agent-1"),
    ("agent", "agent-2"),
    ("agent", "agent-3"),
    ("case", "case-1"),
    ("expect", "expect-1-a"),
    ("scorer", "scorer-a"),
)

fields = [
    (bundle, record, field_name)
    for bundle, record in schemas
    for field_name, field_info in entity_of(bundle).trail_schema.model_fields.items()
    if not (field_info.json_schema_extra or {}).get("exclude_from_fingerprint")
]


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize("bundle, branch_name, field_name", fields)
@pytest.mark.time_machine(datetime(1970, 1, 1, tzinfo=UTC), tick=False)
async def test_identity_boundary(
    inventory_fixture_ts: InventoryTrailSchema,
    time_machine: Any,
    bundle: EntityName,
    branch_name: str,
    field_name: str,
):
    Model = entity_of(bundle).trail_model
    Spec = entity_of(bundle).trail_spec
    Schema = entity_of(bundle).trail_schema

    field = Model._meta.get_field(field_name)

    associated_model = getattr(field, "associated_model", None)
    db_type = field.related_model or associated_model or field.__class__
    api_type = Schema.model_fields[field_name].annotation
    test_key = (db_type, api_type)

    if test_key not in identity_boundary.field_types:
        pytest.fail(f"No test defined for type combination {test_key} on {field_name}")

    schema = getattr(inventory_fixture_ts, bundle)[branch_name]
    _ = await dump_trail_async(Model, schema)
    spec = await load_trail_async(bundle, schema.fingerprint, Spec)

    value, altered_value = identity_boundary.field_types[test_key](
        getattr(schema, field_name)
    )

    for v, altered in (
        (value, False),
        (altered_value, True),
        (value, False),
    ):
        time_machine.shift(timedelta(days=1))
        raw_copy = schema.model_copy(update={field_name: v})

        test_schema = Schema.model_validate(raw_copy.model_dump())
        _ = await dump_trail_async(Model, test_schema)
        test_spec = await load_trail_async(bundle, str(test_schema.fingerprint), Spec)

        if not altered:
            assert schema.fingerprint == test_schema.fingerprint
            assert spec.fingerprint == test_spec.fingerprint

        if altered:
            assert schema.fingerprint != test_schema.fingerprint
            assert spec.fingerprint != test_spec.fingerprint


@pytest.mark.asyncio
@pytest.mark.django_db()
async def test_immutability_trigger(inventory_fixture_ts: InventoryTrailSchema):
    agent_schema = inventory_fixture_ts.agent["agent-1"]
    agent_model = await dump_trail_async(AgentTrailModel, agent_schema)

    with pytest.raises(ProgrammingError):
        await agent_model.asave()

# src/chatddx/django/repo/tests/test_trail.py
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from django.db import ProgrammingError

from chatddx.registry.main import parse_registry
from chatddx.repo.base import (
    TrailModel,
    TrailSchema,
    TrailSpec,
)
from chatddx.repo.main import BundleName, Repo
from chatddx.repo.shufflers.main import dump_trail_async, load_trail_async
from chatddx.repo.tests import identity_boundary
from chatddx.repo.trail_models import AgentTrailModel
from chatddx.repo.trail_schemas import TrailRegistry

registry: TrailRegistry = parse_registry(
    Path(__file__).parent / "data/test-registry.toml",
    schema=TrailRegistry,
)

schemas = (
    ("connection", "connection-1"),
    ("sampling_params", "sampling_params-1"),
    ("tool_group", "tool_group-1"),
    ("tool", "tool-1"),
    ("output_type", "output_type-1"),
    ("agent", "agent-1"),
    ("agent", "agent-2"),
    ("agent", "agent-3"),
    ("case", "case-1"),
)

fields = [
    (bundle, record, field)
    for bundle, record in schemas
    for field in Repo(bundle, TrailSchema).model_fields
]


@pytest.mark.asyncio
@pytest.mark.django_db
@pytest.mark.parametrize("bundle, branch_name, field_name", fields)
@pytest.mark.time_machine(datetime(1970, 1, 1), tick=False)
async def test_identity_boundary(
    time_machine: Any,
    bundle: BundleName,
    branch_name: str,
    field_name: str,
):
    Model = Repo(bundle, TrailModel)
    Spec = Repo(bundle, TrailSpec)
    Schema = Repo(bundle, TrailSchema)

    field = Model._meta.get_field(field_name)

    associated_model = getattr(field, "associated_model", None)
    db_type = field.related_model or associated_model or field.__class__
    api_type = Schema.model_fields[field_name].annotation
    test_key = (db_type, api_type)

    if test_key not in identity_boundary.field_types:
        pytest.fail(f"No test defined for type combination {test_key} on {field_name}")

    schema = getattr(registry, bundle)[branch_name]
    _ = await dump_trail_async(Model, schema)
    spec = await load_trail_async(bundle, schema.fingerprint, Spec)

    value, altered_value = identity_boundary.field_types[test_key](
        getattr(schema, field_name)
    )

    for value, altered in (
        (value, False),
        (altered_value, True),
        (value, False),
    ):
        time_machine.shift(timedelta(days=1))
        raw_copy = schema.model_copy(update={field_name: value})

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
async def test_immutability_trigger():
    agent_schema = registry.agent["agent-1"]
    agent_model = await dump_trail_async(AgentTrailModel, agent_schema)

    with pytest.raises(ProgrammingError):
        await agent_model.asave()

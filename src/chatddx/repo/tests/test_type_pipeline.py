from typing import assert_type

import pytest

from chatddx.core.choices import ToolChoices
from chatddx.core.models import IdentityModel
from chatddx.repo.bundles import bundle_of
from chatddx.repo.entities.agent import (
    AgentBranchSpec,
    AgentTrailSchema,
    AgentTrailSpec,
)
from chatddx.repo.entities.tool.pydantic import ToolFormDataIn, ToolTrailSchema
from chatddx.repo.families.pydantic import BranchSchemaDetails
from chatddx.repo.shufflers.branch import commit, get_branch_model


def test_simple():
    agent_trail_schema = bundle_of("agent").trail_schema

    assert repr(agent_trail_schema) == repr(AgentTrailSchema)
    _ = assert_type(agent_trail_schema, type[AgentTrailSchema])

    agent_trail_spec = bundle_of(agent_trail_schema).trail_spec

    assert repr(agent_trail_spec) == repr(AgentTrailSpec)
    _ = assert_type(agent_trail_spec, type[AgentTrailSpec])

    agent_branch_spec = bundle_of(agent_trail_spec).branch_spec

    assert repr(agent_branch_spec) == repr(AgentBranchSpec)
    _ = assert_type(agent_branch_spec, type[AgentBranchSpec])


def test_super_agent_jsonschema():
    jsonschema = bundle_of("super_agent").form_data_out.model_json_schema(
        mode="serialization"
    )
    assert jsonschema["properties"]["instructions"]["type"] == "string"
    assert jsonschema["properties"]["connection_template"]["type"] == "string"


def test_agent_jsonschema():
    jsonschema = bundle_of("agent").form_data_out.model_json_schema(
        mode="serialization"
    )
    assert jsonschema["properties"]["instructions"]["type"] == "string"
    assert jsonschema["properties"]["connection"]["type"] == "string"

    jsonschema = bundle_of("agent").form_data_in.model_json_schema()
    assert list(jsonschema.keys()) == [
        "$defs",
        "properties",
        "required",
        "title",
        "type",
    ]
    assert list(jsonschema["$defs"].keys()) == [
        "CoercionChoices",
        "ConnectionFormDataIn",
        "IdentitySchemaOut",
        "JsonValue",
        "OutputTypeFormDataIn",
        "ProviderChoices",
        "SamplingParamsFormDataIn",
        "ToolChoices",
        "ToolFormDataIn",
        "ToolGroupFormDataIn",
        "ValidationChoices",
    ]
    assert list(jsonschema["properties"].keys()) == [
        "name",
        "owner",
        "collaborators",
        "tags",
        "instructions",
        "connection",
        "sampling_params",
        "output_type",
        "tool_group",
    ]
    assert jsonschema["properties"]["connection"] == {
        "$ref": "#/$defs/ConnectionFormDataIn"
    }
    assert jsonschema["properties"]["tool_group"] == {
        "$ref": "#/$defs/ToolGroupFormDataIn"
    }


def test_type_pipeline():
    tool_schema_cls = bundle_of("tool").trail_schema
    tool = tool_schema_cls.model_validate(
        {
            "command": "cmd",
            "type": ToolChoices.FUNCTION,
        }
    )
    assert tool.command == "cmd"

    assert bundle_of("tool").form_data_out.model_validate


@pytest.mark.django_db
def test_branch(owner: IdentityModel):

    data = {
        "name": "tool",
        "command": "cmd",
        "type": ToolChoices.FUNCTION,
    }

    form_data = ToolFormDataIn.model_validate(data)
    schema = ToolTrailSchema.model_validate(form_data.model_dump())
    name = form_data.name or ""

    created = commit(
        branch_details=BranchSchemaDetails(
            name=name,
            owner=owner.name,
        ),
        trail=schema,
    )

    tool = get_branch_model(
        "tool",
        owner.name,
        name,
    )
    assert schema.fingerprint == tool.target.fingerprint

    assert created
    assert tool.name == data["name"]

    created = commit(
        branch_details=BranchSchemaDetails(
            name=name,
            owner=owner.name,
        ),
        trail=schema,
    )
    assert not created

    tool = get_branch_model(
        "tool",
        owner.name,
        name,
    )
    assert schema.fingerprint == tool.target.fingerprint
    assert tool.name == data["name"]

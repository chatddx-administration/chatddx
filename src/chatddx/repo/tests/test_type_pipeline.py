from typing import cast

import pytest

from chatddx.core.choices import ToolChoices
from chatddx.core.models import IdentityModel
from chatddx.repo.base import BaseFormDataIn, BaseFormDataOut, TrailSchema
from chatddx.repo.form_data_in import ToolFormDataIn
from chatddx.repo.main import Repo
from chatddx.repo.shufflers.main import dump_branch
from chatddx.repo.trail_schemas import ToolSchema


def test_pydantic_jsonschema():
    jsonschema = Repo("agent", BaseFormDataOut).model_json_schema(mode="serialization")
    assert jsonschema["properties"]["instructions"]["type"] == "string"
    assert jsonschema["properties"]["connection"]["type"] == "string"

    jsonschema = Repo("agent", BaseFormDataIn).model_json_schema()
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
        "IdentitySpec",
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
    # Repo() resolves "tool" -> ToolSchema at runtime via the generic
    # `TrailSchema` slot name, so its static return type is the generic
    # base; cast to what "tool" actually gives back.
    tool_schema_cls = cast(type[ToolSchema], Repo("tool", TrailSchema))
    tool = tool_schema_cls.model_validate(
        {
            "command": "cmd",
            "type": ToolChoices.FUNCTION,
        }
    )
    assert tool.command == "cmd"

    assert Repo("tool", BaseFormDataOut).model_validate


@pytest.mark.django_db
def test_branch():
    owner_name = "alex"
    _, _ = IdentityModel.objects.get_or_create(name=owner_name)

    data = {
        "name": "tool",
        "command": "cmd",
        "type": ToolChoices.FUNCTION,
    }

    form_data = ToolFormDataIn.model_validate(data)
    schema = ToolSchema.model_validate(form_data.model_dump())
    name = form_data.name or ""

    tool, created = dump_branch(
        "tool",
        name,
        owner_name,
        schema,
    )

    assert created
    assert tool.name == data["name"]

    tool, created = dump_branch(
        "tool",
        name,
        owner_name,
        schema,
    )
    assert not created
    assert tool.name == data["name"]

from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, JsonValue

from chatddx.core.choices import ToolChoices
from chatddx.core.fields import TomlString, parse_toml_or_dict, validate_json_schema
from chatddx.repo.families import (
    BranchSchema,
    BranchSpec,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)
from chatddx.repo.families.pydantic import BaseFormDataIn, BaseFormDataOut, BaseTrail


class ToolBasePrimitives(BaseModel):
    command: str
    type: ToolChoices
    description: str = ""


class ToolTrailBase(ToolBasePrimitives, BaseTrail):
    parameters: Annotated[
        dict[str, JsonValue],
        AfterValidator(validate_json_schema),
    ] = Field(default_factory=dict)


class ToolTrailSchema(ToolTrailBase, TrailSchema):
    pass


class ToolTrailSchemaRef(
    TrailSchemaRef,
    ToolTrailBase,
):
    pass


class ToolTrailSpec(ToolTrailBase, TrailSpec):
    pass


class ToolBranchSchema(BranchSchema[ToolTrailSchema]):
    pass


class ToolBranchSpec(BranchSpec[ToolTrailSpec]):
    pass


class ToolFormDataIn(ToolTrailBase, BaseFormDataIn):
    parameters: Annotated[
        dict[str, JsonValue],
        BeforeValidator(parse_toml_or_dict),
    ] = Field(default_factory=dict)


class ToolFormDataOut(ToolBasePrimitives, BaseFormDataOut):
    parameters: TomlString

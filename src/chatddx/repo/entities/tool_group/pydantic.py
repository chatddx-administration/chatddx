from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.tool import ToolFormDataIn, ToolTrailSchema, ToolTrailSpec
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchSchema,
    BranchSpec,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)


class ToolGroupTrailBase(BaseTrail):
    instructions: str


class ToolGroupTrailSchema(ToolGroupTrailBase, TrailSchema):
    tools: list[ToolTrailSchema]


class ToolGroupTrailSchemaRef(
    TrailSchemaRef,
    ToolGroupTrailBase,
):
    pass


class ToolGroupTrailSpec(ToolGroupTrailBase, TrailSpec):
    tools: list[ToolTrailSpec]


class ToolGroupBranchSchema(BranchSchema[ToolGroupTrailSchema]):
    pass


class ToolGroupBranchSpec(BranchSpec[ToolGroupTrailSpec]):
    pass


class ToolGroupFormDataIn(ToolGroupTrailBase, BaseFormDataIn):
    tools: list[ToolFormDataIn] = Field(default_factory=list)


class ToolGroupFormDataOut(ToolGroupTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    tools: list[CoercedStr]

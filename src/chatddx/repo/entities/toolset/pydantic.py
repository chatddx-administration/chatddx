"""
A toolset: a request-time slice. It replaces the tool group
(new-datamodel.md §6).

A variation is ordered tools and the text that fills the instruction's
`tool_guidance` slot. A configuration names one or none, and tools need a
serving with a tool call parser.
"""

from typing import Annotated

from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.tool import ToolFormDataIn, ToolTrailSchema, ToolTrailSpec
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchSchema,
    BranchSpec,
    Details,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)
from chatddx.repo.families.fields import distinct

# the instruction's variable the guidance fills
SLOT = "tool_guidance"


def _name(tool: ToolTrailSchema) -> str:
    return tool.name


class ToolsetTrailBase(BaseTrail):
    guidance: str | None = None


class ToolsetTrailSchema(ToolsetTrailBase, TrailSchema):
    # two tools of one name would be one tool to the model
    tools: Annotated[
        list[ToolTrailSchema],
        Field(min_length=1),
        distinct(_name),
    ]


class ToolsetTrailSchemaRef(TrailSchemaRef, ToolsetTrailBase):
    pass


class ToolsetTrailSpec(ToolsetTrailBase, TrailSpec):
    tools: list[ToolTrailSpec]


class ToolsetBranchSchema(BranchSchema[ToolsetTrailSchema]):
    pass


class ToolsetBranchSpec(BranchSpec[ToolsetTrailSpec, Details]):
    pass


class ToolsetFormDataIn(ToolsetTrailBase, BaseFormDataIn):
    tools: list[ToolFormDataIn] = Field(default_factory=list)


class ToolsetFormDataOut(ToolsetTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    tools: list[CoercedStr]

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
from chatddx.repo.entities.tool import ToolFormDataIn, ToolTrailIn, ToolTrailOut
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchIn,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
    TrailRef,
)
from chatddx.repo.families.fields import distinct

# the instruction's variable the guidance fills
SLOT = "tool_guidance"


def _name(tool: ToolTrailIn) -> str:
    return tool.name


class ToolsetTrailBase(BaseTrail):
    guidance: str | None = None


class ToolsetTrailIn(ToolsetTrailBase, TrailIn):
    # two tools of one name would be one tool to the LLM
    tools: Annotated[
        list[ToolTrailIn],
        Field(min_length=1),
        distinct(_name),
    ]


class ToolsetTrailRef(TrailRef, ToolsetTrailBase):
    pass


class ToolsetTrailOut(ToolsetTrailBase, TrailOut):
    tools: list[ToolTrailOut]


class ToolsetBranchIn(BranchIn[ToolsetTrailIn]):
    pass


class ToolsetBranchOut(BranchOut[ToolsetTrailOut, Details]):
    pass


class ToolsetFormDataIn(ToolsetTrailBase, BaseFormDataIn):
    tools: list[ToolFormDataIn] = Field(default_factory=list)


class ToolsetFormDataOut(ToolsetTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    tools: list[CoercedStr]

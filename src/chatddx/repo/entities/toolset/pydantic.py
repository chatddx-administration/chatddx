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

SLOT = "tool_guidance"


def _name(tool: ToolTrailIn) -> str:
    return tool.name


class ToolsetTrailBase(BaseTrail):
    guidance: str | None = None


class ToolsetTrailIn(ToolsetTrailBase, TrailIn):
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

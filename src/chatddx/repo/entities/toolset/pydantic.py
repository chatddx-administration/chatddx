from typing import Annotated

from pydantic import Field

from chatddx.repo.entities.tool import ToolTrailIn, ToolTrailOut
from chatddx.repo.families import (
    BaseTrail,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
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


class ToolsetTrailOut(ToolsetTrailBase, TrailOut):
    tools: list[ToolTrailOut]


class ToolsetBranchOut(BranchOut[ToolsetTrailOut, Details]):
    pass

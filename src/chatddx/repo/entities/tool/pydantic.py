from typing import Annotated, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from chatddx.repo.families import (
    ORDERED,
    BaseTrail,
    BranchDetails,
    BranchDetailsPatch,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
)
from chatddx.repo.families.fields import EntryPoint, JsonSchema

type ToolName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


class ToolImplementation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    function: EntryPoint


class ToolDetails(Details):
    implementation: ToolImplementation | None = None


class ToolTrailBase(BaseTrail):
    name: ToolName
    description: str = ""
    parameters: JsonSchema = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        json_schema_extra={ORDERED: True},
    )


class ToolTrailIn(ToolTrailBase, TrailIn):
    pass


class ToolTrailOut(ToolTrailBase, TrailOut):
    pass


class ToolBranchDetails(BranchDetails, ToolDetails):
    pass


class ToolBranchDetailsPatch(BranchDetailsPatch, ToolDetails):
    pass


class ToolBranchOut(BranchOut[ToolTrailOut, ToolDetails]):
    pass

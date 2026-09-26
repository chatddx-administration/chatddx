from typing import Annotated, ClassVar

from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from chatddx.core.fields import CoercedStr
from chatddx.repo.families import (
    ORDERED,
    BaseBranch,
    BaseFormDataIn,
    BaseFormDataOut,
    BaseTrail,
    BranchDetails,
    BranchDetailsPatch,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
    TrailRef,
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


class ToolTrailRef(TrailRef, ToolTrailBase):
    pass


class ToolTrailOut(ToolTrailBase, TrailOut):
    pass


class ToolBranchDetails(BranchDetails, ToolDetails):
    pass


class ToolBranchDetailsPatch(BranchDetailsPatch, ToolDetails):
    pass


class ToolBranchIn(BaseBranch[ToolTrailIn], ToolBranchDetails):
    pass


class ToolBranchOut(BranchOut[ToolTrailOut, ToolDetails]):
    pass


class ToolFormDataIn(BaseFormDataIn):
    tool_name: ToolName
    description: str = ""
    parameters: JsonSchema = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
    )
    implementation: ToolImplementation | None = None


class ToolFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    tool_name: str = Field(
        validation_alias=AliasChoices("tool_name", AliasPath("trail", "name"))
    )
    description: str
    parameters: dict[str, object]
    implementation: ToolImplementation | None

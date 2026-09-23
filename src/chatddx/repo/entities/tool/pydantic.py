"""
A tool: what the model sees of a function it can call. It is part of a
toolset, not a slice (new-datamodel.md §6).

The name, description and parameters reach the model, so they are content,
and the parameters keep the order they were written in. What runs when the
model calls it is description: an entry point, and a trial records the
revision it ran.
"""

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
    BranchDetailsPatch,
    BranchSchemaDetails,
    BranchSpec,
    Details,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)
from chatddx.repo.families.fields import JsonSchema

# as the OpenAI API accepts a function's name
type ToolName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


class ToolImplementation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    # `module.path:function`
    entry_point: Annotated[
        str, StringConstraints(pattern=r"^[\w.]+:[A-Za-z_][A-Za-z0-9_]*$")
    ]
    # a git revision, where one is pinned
    rev: str | None = None


class ToolDetails(Details):
    implementation: ToolImplementation | None = None


class ToolTrailBase(BaseTrail):
    # the name the model sees; the branch has a name of its own
    name: ToolName
    description: str = ""
    parameters: JsonSchema = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
        json_schema_extra={ORDERED: True},
    )


class ToolTrailSchema(ToolTrailBase, TrailSchema):
    pass


class ToolTrailSchemaRef(TrailSchemaRef, ToolTrailBase):
    pass


class ToolTrailSpec(ToolTrailBase, TrailSpec):
    pass


class ToolBranchDetails(BranchSchemaDetails, ToolDetails):
    pass


class ToolBranchDetailsPatch(BranchDetailsPatch, ToolDetails):
    pass


class ToolBranchSchema(BaseBranch[ToolTrailSchema], ToolBranchDetails):
    pass


class ToolBranchSpec(BranchSpec[ToolTrailSpec, ToolDetails]):
    pass


# A form has one `name`, the branch's, so the name the model sees is
# `tool_name` there.
class ToolFormDataIn(BaseFormDataIn):
    tool_name: ToolName
    description: str = ""
    parameters: JsonSchema = Field(
        default_factory=lambda: {"type": "object", "properties": {}},
    )
    implementation: ToolImplementation | None = None


class ToolFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    # read from the trail where a form's flat fields hold the branch's name
    tool_name: str = Field(
        validation_alias=AliasChoices("tool_name", AliasPath("target", "name"))
    )
    description: str
    parameters: dict[str, object]
    implementation: ToolImplementation | None

from pydantic import BaseModel, Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.connection import (
    ConnectionFormDataIn,
    ConnectionTrailSchema,
    ConnectionTrailSpec,
)
from chatddx.repo.entities.output_type import (
    OutputTypeFormDataIn,
    OutputTypeTrailSchema,
    OutputTypeTrailSpec,
)
from chatddx.repo.entities.sampling_params import (
    SamplingParamsFormDataIn,
    SamplingParamsTrailSchema,
    SamplingParamsTrailSpec,
)
from chatddx.repo.entities.tool_group import (
    ToolGroupFormDataIn,
    ToolGroupTrailSchema,
    ToolGroupTrailSpec,
)
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
    BranchSchema,
    BranchSpec,
    TrailSchema,
    TrailSchemaRef,
    TrailSpec,
)


class AgentTrailBase(BaseModel):
    instructions: str


class AgentTrailSchema(AgentTrailBase, TrailSchema):
    connection: ConnectionTrailSchema
    sampling_params: SamplingParamsTrailSchema = Field(
        default_factory=SamplingParamsTrailSchema,
    )
    output_type: OutputTypeTrailSchema = Field(
        default_factory=lambda: OutputTypeTrailSchema(
            definition={},
        ),
    )
    tool_group: ToolGroupTrailSchema = Field(
        default_factory=lambda: ToolGroupTrailSchema(
            instructions="",
            tools=[],
        ),
    )


class AgentTrailSchemaRef(AgentTrailBase, TrailSchemaRef):
    connection_id: int
    sampling_params_id: int
    output_type_id: int
    tool_group_id: int


class AgentTrailSpec(AgentTrailBase, TrailSpec):
    connection: ConnectionTrailSpec
    sampling_params: SamplingParamsTrailSpec
    output_type: OutputTypeTrailSpec
    tool_group: ToolGroupTrailSpec


class AgentBranchSchema(BranchSchema[AgentTrailSchema]):
    pass


class AgentBranchSpec(BranchSpec[AgentTrailSpec]):
    pass


class AgentFormDataIn(AgentTrailBase, BaseFormDataIn):
    connection: ConnectionFormDataIn
    sampling_params: SamplingParamsFormDataIn
    output_type: OutputTypeFormDataIn
    tool_group: ToolGroupFormDataIn


class AgentFormDataOut(AgentTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    connection: CoercedStr
    sampling_params: CoercedStr
    output_type: CoercedStr
    tool_group: CoercedStr

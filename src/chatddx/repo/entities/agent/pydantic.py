"""
An agent, which is nothing but what it points at.

Every field here is a relation: its instruction, its connection, its
sampling params, its output type, its tool group. The instruction used to
be the one primitive on the agent, and it is a bundle of its own now (see
`chatddx.repo.entities.instruction`) -- so there is no value an agent
holds that is not some other entity's to hold.

The flat forms still show the instruction as a textarea, which is what
`DefinitionText` and `as_definition` are for: the form data in and out of
this entity carry the text where the trail carries the bundle.
"""

from typing import Annotated

from pydantic import BeforeValidator, Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.connection import (
    ConnectionFormDataIn,
    ConnectionTrailSchema,
    ConnectionTrailSpec,
)
from chatddx.repo.entities.instruction import (
    DefinitionText,
    InstructionFormDataIn,
    InstructionTrailSchema,
    InstructionTrailSpec,
    as_definition,
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


class AgentTrailSchema(TrailSchema):
    instruction: InstructionTrailSchema
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


class AgentTrailSchemaRef(TrailSchemaRef):
    instruction_id: int
    connection_id: int
    sampling_params_id: int
    output_type_id: int
    tool_group_id: int


class AgentTrailSpec(TrailSpec):
    instruction: InstructionTrailSpec
    connection: ConnectionTrailSpec
    sampling_params: SamplingParamsTrailSpec
    output_type: OutputTypeTrailSpec
    tool_group: ToolGroupTrailSpec


class AgentBranchSchema(BranchSchema[AgentTrailSchema]):
    pass


class AgentBranchSpec(BranchSpec[AgentTrailSpec]):
    pass


class AgentFormDataIn(BaseFormDataIn):
    # the textarea hands over the text; the bundle is what it stands for
    instruction: Annotated[
        InstructionFormDataIn,
        BeforeValidator(as_definition),
    ]
    connection: ConnectionFormDataIn
    sampling_params: SamplingParamsFormDataIn
    output_type: OutputTypeFormDataIn
    tool_group: ToolGroupFormDataIn


class AgentFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    instruction: DefinitionText
    connection: CoercedStr
    sampling_params: CoercedStr
    output_type: CoercedStr
    tool_group: CoercedStr

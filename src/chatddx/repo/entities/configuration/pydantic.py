"""
A configuration: a composition of one variation of each request-time slice,
and optionally a toolset. It replaces the agent (new-datamodel.md §6).

It holds no model. The stack is chosen per trial, so one configuration runs
on every model, and a cell joins a configuration to a stack. Resolution
turns the cell into a request, or says why it can't (§9).

The flat form the super agent had is the configuration's: its relations are
templates chosen from, not forms of their own (§7, Views).
"""

from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.coercion import (
    CoercionFormDataIn,
    CoercionTrailSchema,
    CoercionTrailSpec,
)
from chatddx.repo.entities.instruction import (
    InstructionFormDataIn,
    InstructionTrailSchema,
    InstructionTrailSpec,
)
from chatddx.repo.entities.output import (
    OutputFormDataIn,
    OutputTrailSchema,
    OutputTrailSpec,
)
from chatddx.repo.entities.reasoning import (
    ReasoningFormDataIn,
    ReasoningTrailSchema,
    ReasoningTrailSpec,
)
from chatddx.repo.entities.sampling import (
    SamplingFormDataIn,
    SamplingTrailSchema,
    SamplingTrailSpec,
)
from chatddx.repo.entities.toolset import (
    ToolsetFormDataIn,
    ToolsetTrailSchema,
    ToolsetTrailSpec,
)
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


class ConfigurationTrailBase(BaseTrail):
    pass


class ConfigurationTrailSchema(ConfigurationTrailBase, TrailSchema):
    instruction: InstructionTrailSchema
    output: OutputTrailSchema
    coercion: CoercionTrailSchema
    reasoning: ReasoningTrailSchema
    sampling: SamplingTrailSchema
    toolset: ToolsetTrailSchema | None = None


class ConfigurationTrailSchemaRef(TrailSchemaRef, ConfigurationTrailBase):
    instruction_id: int
    output_id: int
    coercion_id: int
    reasoning_id: int
    sampling_id: int
    toolset_id: int | None


class ConfigurationTrailSpec(ConfigurationTrailBase, TrailSpec):
    instruction: InstructionTrailSpec
    output: OutputTrailSpec
    coercion: CoercionTrailSpec
    reasoning: ReasoningTrailSpec
    sampling: SamplingTrailSpec
    toolset: ToolsetTrailSpec | None


class ConfigurationBranchSchema(BranchSchema[ConfigurationTrailSchema]):
    pass


class ConfigurationBranchSpec(BranchSpec[ConfigurationTrailSpec, Details]):
    pass


class ConfigurationFormDataIn(ConfigurationTrailBase, BaseFormDataIn):
    instruction: InstructionFormDataIn
    output: OutputFormDataIn
    coercion: CoercionFormDataIn
    reasoning: ReasoningFormDataIn
    sampling: SamplingFormDataIn
    toolset: ToolsetFormDataIn | None = None


class ConfigurationFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    instruction: CoercedStr = Field(serialization_alias="instruction_template")
    output: CoercedStr = Field(serialization_alias="output_template")
    coercion: CoercedStr = Field(serialization_alias="coercion_template")
    reasoning: CoercedStr = Field(serialization_alias="reasoning_template")
    sampling: CoercedStr = Field(serialization_alias="sampling_template")
    toolset: CoercedStr | None = Field(serialization_alias="toolset_template")

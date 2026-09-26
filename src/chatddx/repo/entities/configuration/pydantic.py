from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.coercion import (
    CoercionFormDataIn,
    CoercionTrailIn,
    CoercionTrailOut,
)
from chatddx.repo.entities.instruction import (
    InstructionFormDataIn,
    InstructionTrailIn,
    InstructionTrailOut,
)
from chatddx.repo.entities.output import (
    OutputFormDataIn,
    OutputTrailIn,
    OutputTrailOut,
)
from chatddx.repo.entities.reasoning import (
    ReasoningFormDataIn,
    ReasoningTrailIn,
    ReasoningTrailOut,
)
from chatddx.repo.entities.sampling import (
    SamplingFormDataIn,
    SamplingTrailIn,
    SamplingTrailOut,
)
from chatddx.repo.entities.toolset import (
    ToolsetFormDataIn,
    ToolsetTrailIn,
    ToolsetTrailOut,
)
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


class ConfigurationTrailBase(BaseTrail):
    pass


class ConfigurationTrailIn(ConfigurationTrailBase, TrailIn):
    instruction: InstructionTrailIn
    output: OutputTrailIn
    coercion: CoercionTrailIn
    reasoning: ReasoningTrailIn
    sampling: SamplingTrailIn
    toolset: ToolsetTrailIn | None = None


class ConfigurationTrailRef(TrailRef, ConfigurationTrailBase):
    instruction_id: int
    output_id: int
    coercion_id: int
    reasoning_id: int
    sampling_id: int
    toolset_id: int | None


class ConfigurationTrailOut(ConfigurationTrailBase, TrailOut):
    instruction: InstructionTrailOut
    output: OutputTrailOut
    coercion: CoercionTrailOut
    reasoning: ReasoningTrailOut
    sampling: SamplingTrailOut
    toolset: ToolsetTrailOut | None


class ConfigurationBranchIn(BranchIn[ConfigurationTrailIn]):
    pass


class ConfigurationBranchOut(BranchOut[ConfigurationTrailOut, Details]):
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

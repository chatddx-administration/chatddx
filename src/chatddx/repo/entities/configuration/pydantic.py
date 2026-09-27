from chatddx.repo.entities.coercion import (
    CoercionTrailIn,
    CoercionTrailOut,
)
from chatddx.repo.entities.instruction import (
    InstructionTrailIn,
    InstructionTrailOut,
)
from chatddx.repo.entities.output import (
    OutputTrailIn,
    OutputTrailOut,
)
from chatddx.repo.entities.reasoning import (
    ReasoningTrailIn,
    ReasoningTrailOut,
)
from chatddx.repo.entities.sampling import (
    SamplingTrailIn,
    SamplingTrailOut,
)
from chatddx.repo.entities.toolset import (
    ToolsetTrailIn,
    ToolsetTrailOut,
)
from chatddx.repo.families import (
    BaseTrail,
    BranchOut,
    Details,
    TrailIn,
    TrailOut,
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


class ConfigurationTrailOut(ConfigurationTrailBase, TrailOut):
    instruction: InstructionTrailOut
    output: OutputTrailOut
    coercion: CoercionTrailOut
    reasoning: ReasoningTrailOut
    sampling: SamplingTrailOut
    toolset: ToolsetTrailOut | None


class ConfigurationBranchOut(BranchOut[ConfigurationTrailOut, Details]):
    pass

from chatddx.repo.base import BranchSpec
from chatddx.repo.trail_specs import (
    AgentSpec,
    CaseSpec,
    ConnectionSpec,
    OutputTypeSpec,
    SamplingParamsSpec,
    ToolGroupSpec,
    ToolSpec,
)


class CaseBranchSpec(BranchSpec[CaseSpec]):
    target: CaseSpec


class ConnectionBranchSpec(BranchSpec[ConnectionSpec]):
    target: ConnectionSpec


class SamplingParamsBranchSpec(BranchSpec[SamplingParamsSpec]):
    target: SamplingParamsSpec


class OutputTypeBranchSpec(BranchSpec[OutputTypeSpec]):
    target: OutputTypeSpec


class ToolBranchSpec(BranchSpec[ToolSpec]):
    target: ToolSpec


class ToolGroupBranchSpec(BranchSpec[ToolGroupSpec]):
    target: ToolGroupSpec


class AgentBranchSpec(BranchSpec[AgentSpec]):
    target: AgentSpec

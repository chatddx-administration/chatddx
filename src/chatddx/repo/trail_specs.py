# src/chatddx/repo/trail_specs.py
from pydantic import (
    BaseModel,
)

from chatddx.repo.base import TrailSpec
from chatddx.repo.trail_schemas import (
    CaseBase,
    ConnectionBase,
    ExpectBase,
    OutputTypeBase,
    SamplingParamsBase,
    ToolBase,
    ToolGroupBase,
)


class CaseSpec(CaseBase, TrailSpec):
    pass


class ConnectionSpec(ConnectionBase, TrailSpec):
    pass


class SamplingParamsSpec(SamplingParamsBase, TrailSpec):
    pass


class OutputTypeSpec(OutputTypeBase, TrailSpec):
    pass


class ExpectSpec(ExpectBase, TrailSpec):
    case: CaseSpec
    output_type: OutputTypeSpec


class ToolSpec(ToolBase, TrailSpec):
    pass


class ToolGroupSpec(ToolGroupBase, TrailSpec):
    tools: list[ToolSpec]


class AgentBase(BaseModel):
    instructions: str


class AgentSpec(AgentBase, TrailSpec):
    connection: ConnectionSpec
    sampling_params: SamplingParamsSpec
    output_type: OutputTypeSpec
    tool_group: ToolGroupSpec

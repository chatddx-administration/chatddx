from chatddx.registry.schemas import RegistryInstance
from chatddx.repo.base import TrailSchemaRef
from chatddx.repo.trail_schemas import (
    AgentBase,
    CaseBase,
    ConnectionBase,
    OutputTypeBase,
    SamplingParamsBase,
    ToolBase,
    ToolGroupBase,
)


class ToolGroupSchemaRef(
    TrailSchemaRef,
    ToolGroupBase,
    RegistryInstance,
):
    tools: list[int]
    pass


class AgentSchemaRef(
    TrailSchemaRef,
    AgentBase,
    RegistryInstance,
):
    connection_id: int
    sampling_params_id: int
    output_type_id: int
    tool_group_id: int
    pass


class ConnectionSchemaRef(
    TrailSchemaRef,
    ConnectionBase,
    RegistryInstance,
):
    pass


class SamplingParamsSchemaRef(
    TrailSchemaRef,
    SamplingParamsBase,
    RegistryInstance,
):
    pass


class OutputTypeSchemaRef(
    TrailSchemaRef,
    OutputTypeBase,
    RegistryInstance,
):
    pass


class ToolSchemaRef(
    TrailSchemaRef,
    ToolBase,
    RegistryInstance,
):
    pass


class CaseSchemaRef(
    TrailSchemaRef,
    CaseBase,
    RegistryInstance,
):
    pass

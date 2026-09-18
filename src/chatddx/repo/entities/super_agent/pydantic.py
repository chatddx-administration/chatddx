from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.agent.pydantic import AgentTrailBase
from chatddx.repo.entities.connection import ConnectionFormDataIn
from chatddx.repo.entities.output_type import OutputTypeFormDataIn
from chatddx.repo.entities.sampling_params import SamplingParamsFormDataIn
from chatddx.repo.entities.tool_group import ToolGroupFormDataIn
from chatddx.repo.families import (
    BaseFormDataIn,
    BaseFormDataOut,
)


class SuperAgentFormDataIn(AgentTrailBase, BaseFormDataIn):
    connection: ConnectionFormDataIn
    sampling_params: SamplingParamsFormDataIn
    output_type: OutputTypeFormDataIn
    tool_group: ToolGroupFormDataIn


class SuperAgentFormDataOut(AgentTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    connection: CoercedStr = Field(serialization_alias="connection_template")
    sampling_params: CoercedStr = Field(serialization_alias="sampling_params_template")
    output_type: CoercedStr = Field(serialization_alias="output_type_template")
    tool_group: CoercedStr = Field(serialization_alias="tool_group_template")

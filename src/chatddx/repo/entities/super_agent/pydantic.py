from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.agent.pydantic import AgentTrailBase
from chatddx.repo.families import (
    BaseFormDataOut,
)


# There is no SuperAgentFormDataIn: the flat form validates as an agent
# (see `SuperAgentForm.entity_name`), and only what it renders differs.
class SuperAgentFormDataOut(AgentTrailBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    connection: CoercedStr = Field(serialization_alias="connection_template")
    sampling_params: CoercedStr = Field(serialization_alias="sampling_params_template")
    output_type: CoercedStr = Field(serialization_alias="output_type_template")
    tool_group: CoercedStr = Field(serialization_alias="tool_group_template")

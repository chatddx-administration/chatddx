from pydantic import Field

from chatddx.core.fields import CoercedStr
from chatddx.repo.entities.instruction import DefinitionText
from chatddx.repo.families import (
    BaseFormDataOut,
)


# There is no SuperAgentFormDataIn: the flat form validates as an agent
# (see `SuperAgentForm.entity_name`), and only what it renders differs.
class SuperAgentFormDataOut(BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    # the one relation this form renders inline rather than as a subform
    instruction: DefinitionText
    connection: CoercedStr = Field(serialization_alias="connection_template")
    sampling_params: CoercedStr = Field(serialization_alias="sampling_params_template")
    output_type: CoercedStr = Field(serialization_alias="output_type_template")
    tool_group: CoercedStr = Field(serialization_alias="tool_group_template")

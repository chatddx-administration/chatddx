# src/chatddx/repo/form_data_out.py
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

from chatddx.core.fields import CoercedStr, dict_to_toml, list_to_text
from chatddx.repo.base import BaseFormDataOut
from chatddx.repo.trail_schemas import (
    AgentBase,
    CaseBase,
    ConnectionBasePrimitives,
    OutputTypeBasePrimitives,
    SamplingParamsBasePrimitives,
    ToolBasePrimitives,
    ToolGroupBase,
)

TomlString = Annotated[str, BeforeValidator(dict_to_toml)]
TextList = Annotated[str, BeforeValidator(list_to_text)]


class TemplateData(BaseModel):
    agent: dict[str, AgentFormDataOut] = Field(default_factory=dict)
    connection: dict[str, ConnectionFormDataOut] = Field(default_factory=dict)
    sampling_params: dict[str, SamplingParamsFormDataOut] = Field(default_factory=dict)
    output_type: dict[str, OutputTypeFormDataOut] = Field(default_factory=dict)
    tool_group: dict[str, ToolGroupFormDataOut] = Field(default_factory=dict)
    tool: dict[str, ToolFormDataOut] = Field(default_factory=dict)
    case: dict[str, CaseFormDataOut] = Field(default_factory=dict)


class CaseFormDataOut(CaseBase, BaseFormDataOut):
    pass


class ToolFormDataOut(ToolBasePrimitives, BaseFormDataOut):
    parameters: TomlString


class ConnectionFormDataOut(ConnectionBasePrimitives, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    profile: TomlString


class SamplingParamsFormDataOut(SamplingParamsBasePrimitives, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    logit_bias: TomlString
    provider_params: TomlString
    stop_sequences: TextList


class OutputTypeFormDataOut(OutputTypeBasePrimitives, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    definition: TomlString


class ToolGroupFormDataOut(ToolGroupBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    tools: list[CoercedStr]


class AgentFormDataOut(AgentBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    connection: CoercedStr
    sampling_params: CoercedStr
    output_type: CoercedStr
    tool_group: CoercedStr


class SuperAgentFormDataOut(AgentBase, BaseFormDataOut):
    id: CoercedStr = Field(serialization_alias="template")
    connection: CoercedStr = Field(serialization_alias="connection_template")
    sampling_params: CoercedStr = Field(serialization_alias="sampling_params_template")
    output_type: CoercedStr = Field(serialization_alias="output_type_template")
    tool_group: CoercedStr = Field(serialization_alias="tool_group_template")

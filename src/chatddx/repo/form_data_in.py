# src/chatddx/repo/form_data_in.py
from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, Field, JsonValue

from chatddx.core.decimals import SamplingDecimal
from chatddx.core.fields import parse_text_or_list, parse_toml_or_dict
from chatddx.repo.base import BaseFormDataIn
from chatddx.repo.trail_schemas import (
    AgentBase,
    CaseBase,
    ConnectionBase,
    OutputTypeBase,
    SamplingParamsBase,
    ToolBase,
    ToolGroupBase,
)


class CaseFormDataIn(CaseBase, BaseFormDataIn):
    pass


class ToolFormDataIn(ToolBase, BaseFormDataIn):
    parameters: Annotated[
        dict[str, JsonValue],
        BeforeValidator(parse_toml_or_dict),
    ] = Field(default_factory=dict)


class ConnectionFormDataIn(ConnectionBase, BaseFormDataIn):
    profile: Annotated[
        dict[str, JsonValue],
        BeforeValidator(parse_toml_or_dict),
    ] = Field(default_factory=dict)


class SamplingParamsFormDataIn(SamplingParamsBase, BaseFormDataIn):
    stop_sequences: Annotated[
        list[str],
        BeforeValidator(parse_text_or_list),
    ] = Field(default_factory=list)
    logit_bias: Annotated[
        dict[str, SamplingDecimal],
        BeforeValidator(parse_toml_or_dict),
    ] = Field(default_factory=dict)

    provider_params: Annotated[
        dict[str, JsonValue],
        BeforeValidator(parse_toml_or_dict),
    ] = Field(default_factory=dict)


class OutputTypeFormDataIn(OutputTypeBase, BaseFormDataIn):
    definition: Annotated[
        dict[str, JsonValue],
        BeforeValidator(parse_toml_or_dict),
    ] = Field(default_factory=dict)


class ToolGroupFormDataIn(ToolGroupBase, BaseFormDataIn):
    tools: list[ToolFormDataIn] = Field(default_factory=list)


class SubAgentFormDataIn(AgentBase, BaseFormDataIn):
    pass


class AgentFormDataIn(AgentBase, BaseFormDataIn):
    connection: ConnectionFormDataIn
    sampling_params: SamplingParamsFormDataIn
    output_type: OutputTypeFormDataIn
    tool_group: ToolGroupFormDataIn


class SuperAgentFormDataIn(AgentBase, BaseFormDataIn):
    connection: ConnectionFormDataIn
    sampling_params: SamplingParamsFormDataIn
    output_type: OutputTypeFormDataIn
    tool_group: ToolGroupFormDataIn

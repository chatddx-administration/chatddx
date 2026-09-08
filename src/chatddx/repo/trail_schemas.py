# src/chatddx/django/repo/trail_schemas.py
from __future__ import annotations

from typing import Annotated, override

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    HttpUrl,
    JsonValue,
)

from chatddx.core.choices import (
    CoercionChoices,
    ProviderChoices,
    ToolChoices,
    ValidationChoices,
)
from chatddx.core.decimals import SamplingDecimal
from chatddx.core.fields import validate_json_schema
from chatddx.registry.schemas import BaseRegistry
from chatddx.repo.base import TrailSchema


class TrailRegistry(BaseRegistry):
    agent: dict[str, AgentSchema] = Field(default_factory=dict)
    connection: dict[str, ConnectionSchema] = Field(default_factory=dict)
    sampling_params: dict[str, SamplingParamsSchema] = Field(default_factory=dict)
    tool_group: dict[str, ToolGroupSchema] = Field(default_factory=dict)
    tool: dict[str, ToolSchema] = Field(default_factory=dict)
    output_type: dict[str, OutputTypeSchema] = Field(default_factory=dict)


class ConnectionBasePrimitives(BaseModel):
    provider: ProviderChoices
    model: str
    endpoint: HttpUrl


class ConnectionBase(ConnectionBasePrimitives):
    profile: dict[str, JsonValue] = Field(default_factory=dict)


class ConnectionSchema(ConnectionBase, TrailSchema):
    pass


class SamplingParamsBasePrimitives(BaseModel):
    temperature: SamplingDecimal | None = None
    top_p: SamplingDecimal | None = None
    top_k: int | None = None
    max_tokens: int | None = None
    seed: int | None = None
    n: int | None = None
    presence_penalty: SamplingDecimal | None = None
    frequency_penalty: SamplingDecimal | None = None


class SamplingParamsBase(SamplingParamsBasePrimitives):
    stop_sequences: list[str] = Field(default_factory=list)
    logit_bias: dict[str, SamplingDecimal] = Field(default_factory=dict)
    provider_params: dict[str, JsonValue] = Field(default_factory=dict)


class SamplingParamsSchema(SamplingParamsBase, TrailSchema):
    pass


class OutputTypeBasePrimitives(BaseModel):
    output_retries: int = 1
    validation_strategy: ValidationChoices = ValidationChoices.INFORM
    coercion_strategy: CoercionChoices = CoercionChoices.NATIVE


class OutputTypeBase(OutputTypeBasePrimitives):
    definition: Annotated[
        dict[str, JsonValue],
        AfterValidator(validate_json_schema),
    ] = Field(default_factory=dict)


class OutputTypeSchema(OutputTypeBase, TrailSchema):
    pass


class ToolBasePrimitives(BaseModel):
    command: str
    type: ToolChoices
    description: str = ""


class ToolBase(ToolBasePrimitives):
    parameters: Annotated[
        dict[str, JsonValue],
        AfterValidator(validate_json_schema),
    ] = Field(default_factory=dict)


class ToolSchema(ToolBase, TrailSchema):
    pass


class ToolGroupBase(BaseModel):
    instructions: str


class ToolGroupSchema(ToolGroupBase, TrailSchema):
    tools: list[ToolSchema]

    @override
    def as_fingerprint(self):
        from chatddx.utils import generate_fingerprint

        serialized = self.model_dump(exclude={"fingerprint", "tools"})
        fingerprints = {"tools": [ref.as_fingerprint() for ref in self.tools]}

        return generate_fingerprint(serialized | fingerprints)


class AgentBase(BaseModel):
    instructions: str


class AgentSchema(AgentBase, TrailSchema):
    connection: ConnectionSchema
    sampling_params: SamplingParamsSchema = Field(
        default_factory=SamplingParamsSchema,
    )
    output_type: OutputTypeSchema = Field(
        default_factory=lambda: OutputTypeSchema(
            definition={},
        ),
    )
    tool_group: ToolGroupSchema = Field(
        default_factory=lambda: ToolGroupSchema(
            instructions="",
            tools=[],
        ),
    )

    @override
    def as_fingerprint(self):
        from chatddx.utils import generate_fingerprint

        relations = {"connection", "sampling_params", "output_type", "tool_group"}

        serialized = self.model_dump(exclude={"fingerprint"} | relations)
        fingerprints = {ref: getattr(self, ref).as_fingerprint() for ref in relations}

        return generate_fingerprint(serialized | fingerprints)

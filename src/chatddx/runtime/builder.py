# src/chatddx/runtime/builder.py
from decimal import Decimal
from typing import Any, get_args

import jsonschema
from jinja2 import Template
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai import (
    ModelProfile,
    ModelRetry,
    ModelSettings,
    RunContext,
    StructuredDict,
)
from pydantic_ai import Tool as PydanticTool
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import StructuredOutputMode
from pydantic_ai.providers.openai import OpenAIProvider

from chatddx.core.choices import ToolChoices, ValidationChoices
from chatddx.repo.trail_specs import AgentSpec, SamplingParamsSpec, ToolGroupSpec
from chatddx.runtime import tools
from chatddx.runtime.context import AgentContext, OutputType


def build_agent(
    agent_spec: AgentSpec,
    output_type: type[OutputType],
    api_key: str | None = None,
) -> PydanticAgent[AgentContext, OutputType]:

    model: OpenAIChatModel = build_model(agent_spec, api_key)
    model_settings = build_config(agent_spec.sampling_params)
    tool_group_instructions, tools = build_tools(agent_spec.tool_group)

    instructions = Template(agent_spec.instructions).render(
        tool_group_instructions=tool_group_instructions,
    )

    pydantic_agent = PydanticAgent[AgentContext, OutputType](
        model,
        name=agent_spec.fingerprint,
        instructions=instructions,
        tools=tools,
        retries={"output": agent_spec.output_type.output_retries},
        deps_type=AgentContext,
        output_type=output_type,
        model_settings=model_settings,
    )

    _ = pydantic_agent.output_validator(validate_output)

    return pydantic_agent


def build_model(
    agent_spec: AgentSpec,
    api_key: str | None = None,
):
    model_kwargs: dict[str, Any] = {}
    profile_kwargs: dict[str, Any] = agent_spec.connection.profile.copy()

    if agent_spec.output_type.coercion_strategy in get_args(StructuredOutputMode):
        profile_kwargs["default_structured_output_mode"] = (
            agent_spec.output_type.coercion_strategy
        )

    model_kwargs["profile"] = ModelProfile(**profile_kwargs)
    model_kwargs["model_name"] = agent_spec.connection.model

    model_kwargs["provider"] = OpenAIProvider(
        base_url=str(agent_spec.connection.endpoint),
        api_key=api_key,
    )

    return OpenAIChatModel(**model_kwargs)


def build_config(sampling_params_spec: SamplingParamsSpec) -> ModelSettings:
    settings = sampling_params_spec.model_dump(
        exclude_none=True,
        exclude={"id", "timestamp", "fingerprint"},
    )
    provider_params = settings.pop("provider_params")

    return ModelSettings(settings | provider_params)


def build_tools(
    tool_group_spec: ToolGroupSpec,
) -> tuple[str, list[PydanticTool]]:
    return tool_group_spec.instructions, [
        PydanticTool(
            getattr(tools, tool_spec.command),
            takes_ctx=True,
        )
        for tool_spec in tool_group_spec.tools
        if tool_spec.type == ToolChoices.FUNCTION
    ]


def build_output_type(agent_spec: AgentSpec) -> type[OutputType]:
    schema = agent_spec.output_type.definition
    match schema.get("type"):
        case "bool":
            return bool
        case "integer":
            return int
        case "number":
            return Decimal
        case "array":
            return list
        case "object":
            return StructuredDict(schema)
        case None:
            return str
        case _ as invalid_type:
            raise ValueError(f"Unexpected output type '{invalid_type}'")


async def validate_output(
    ctx: RunContext[AgentContext],
    output: OutputType,
) -> OutputType:
    strategy = ctx.deps.agent.output_type.validation_strategy

    if strategy == ValidationChoices.NOOP:
        return output

    if ctx.partial_output:
        return output

    if not (isinstance(output, dict) and ctx.deps.agent.output_type):
        return output

    try:
        jsonschema.validate(
            instance=output, schema=ctx.deps.agent.output_type.definition
        )
        return output
    except jsonschema.ValidationError as e:
        match strategy:
            case ValidationChoices.INFORM:
                return output | {"__error__": e.message}
            case ValidationChoices.RETRY:
                raise ModelRetry(e.message) from e
            case ValidationChoices.CRASH:
                raise RuntimeError(f"Validation failed: {e.message}") from e

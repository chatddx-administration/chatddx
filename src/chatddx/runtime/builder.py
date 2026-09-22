# src/chatddx/runtime/builder.py
import logging
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, cast, get_args

import jsonschema
from jinja2 import Template
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_ai import (
    Agent as PydanticAgent,
    ModelProfile,
    ModelRetry,
    ModelSettings,
    RunContext,
    StructuredDict,
    Tool as PydanticTool,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.output import StructuredOutputMode
from pydantic_ai.profiles import InlineDefsJsonSchemaTransformer
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_core import CoreSchema, core_schema

from chatddx.core.choices import ToolChoices, ValidationChoices
from chatddx.repo.entities.agent.pydantic import AgentTrailSpec
from chatddx.repo.entities.output_type.pydantic import is_free_text
from chatddx.repo.entities.sampling_params.pydantic import SamplingParamsTrailSpec
from chatddx.repo.entities.tool_group.pydantic import ToolGroupTrailSpec
from chatddx.runtime import tools
from chatddx.runtime.context import AgentContext, OutputType

logger = logging.getLogger(__name__)


def build_agent(
    agent_spec: AgentTrailSpec,
    output_type: type[OutputType],
    api_key: str | None = None,
) -> PydanticAgent[AgentContext, OutputType]:

    model: OpenAIChatModel = build_model(agent_spec, api_key)
    model_settings = build_config(agent_spec.sampling_params)
    tool_group_instructions, tools = build_tools(agent_spec.tool_group)

    instructions = Template(agent_spec.instruction.definition).render(
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
    agent_spec: AgentTrailSpec,
    api_key: str | None = None,
):
    model_kwargs: dict[str, Any] = {}
    profile_kwargs: dict[str, Any] = agent_spec.connection.profile.copy()

    # An output type that pins a strategy overrides the connection's; one
    # that leaves it at `auto` takes whatever the connection's profile says.
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


def build_config(sampling_params_spec: SamplingParamsTrailSpec) -> ModelSettings:
    exclude: set[str] = set()

    if not sampling_params_spec.logit_bias:
        exclude |= {"logit_bias"}

    settings = sampling_params_spec.model_dump(
        exclude_none=True,
        exclude={"id", "timestamp", "fingerprint"} | exclude,
    )
    provider_params = settings.pop("provider_params")

    return ModelSettings(settings | provider_params)


def build_tools(
    tool_group_spec: ToolGroupTrailSpec,
) -> tuple[str, list[PydanticTool]]:
    return tool_group_spec.instructions, [
        PydanticTool(
            getattr(tools, tool_spec.command),
            takes_ctx=True,
        )
        for tool_spec in tool_group_spec.tools
        if tool_spec.type == ToolChoices.FUNCTION
    ]


# pydantic-ai asks for an output that is not an object as the one field of
# one, under this name (`ObjectOutputProcessor.outer_typed_dict_key`): tool
# arguments, and most structured output APIs, take nothing else.
ENVELOPE = "response"


def build_output_type(agent_spec: AgentTrailSpec) -> type[OutputType]:
    """
    What pydantic-ai is asked for: text where the output type's definition
    names no type, and otherwise a type whose JSON Schema is the definition
    as written -- an array keeps its items, a description reaches the model
    -- whichever coercion strategy carries it.
    """
    definition = agent_spec.output_type.definition

    if is_free_text(definition):
        return str

    if definition["type"] == "object":
        return StructuredDict(deepcopy(definition))

    return structured_value(definition)


def structured_value(definition: Mapping[str, Any]) -> type[OutputType]:
    """
    A type whose JSON Schema is `definition`, for an output that is not an
    object; `StructuredDict` is its counterpart for one that is.

    pydantic-ai asks the model for it inside an `ENVELOPE` and hands back
    what is in it, so a run returns the value itself. Whether that value is
    valid against the definition is `validate_output`'s to say.
    """
    # Nested under the envelope, `$defs` would be out of reach of the
    # references into them, as `StructuredDict` also finds.
    schema = InlineDefsJsonSchemaTransformer(deepcopy(dict(definition))).walk()

    if "$defs" in schema:
        raise ValueError("an output type that refers to itself cannot be asked for")

    class _StructuredValue:
        @classmethod
        def __get_pydantic_core_schema__(
            cls,
            source_type: Any,
            handler: GetCoreSchemaHandler,
        ) -> CoreSchema:
            return core_schema.any_schema()

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            core_schema: CoreSchema,
            handler: GetJsonSchemaHandler,
        ) -> JsonSchemaValue:
            return deepcopy(schema)

    # what the output is called where a mode names it, as `StructuredDict`
    # takes it from the title
    _StructuredValue.__name__ = str(definition.get("title") or "output")

    # a stand-in for its schema: what a run returns is the JSON value itself
    return cast(type[OutputType], _StructuredValue)


def unwrap(definition: Mapping[str, Any], data: Any) -> Any:
    """
    The output a reply carried, from the JSON the model wrote: all of it for
    an object, and what is in the `ENVELOPE` it was asked for otherwise.
    """
    if is_free_text(definition) or definition["type"] == "object":
        return data

    envelope: Any = data

    if isinstance(envelope, dict) and ENVELOPE in envelope:
        return cast(dict[str, Any], envelope)[ENVELOPE]

    return data


async def validate_output(
    ctx: RunContext[AgentContext],
    output: OutputType,
) -> OutputType:
    strategy = ctx.deps.agent.output_type.validation_strategy
    definition = ctx.deps.agent.output_type.definition

    if strategy == ValidationChoices.NOOP:
        return output

    if ctx.partial_output:
        return output

    # free text has nothing to be valid against
    if is_free_text(definition):
        return output

    try:
        jsonschema.validate(instance=output, schema=definition)
        return output
    except jsonschema.ValidationError as e:
        match strategy:
            case ValidationChoices.INFORM:
                return inform(output, e.message)
            case ValidationChoices.RETRY:
                raise ModelRetry(e.message) from e
            case ValidationChoices.CRASH:
                raise RuntimeError(f"Validation failed: {e.message}") from e


def inform(output: OutputType, message: str) -> OutputType:
    """
    An output that failed validation, marked as such where it has room for
    the mark: an object carries it as `__error__`. A list or a bare value has
    no field to put it in, so it goes on unmarked -- the log says what was
    wrong, and a scorer checks what it is handed against what it accepts.
    """
    if isinstance(output, dict):
        return output | {"__error__": message}

    logger.warning("an output failed validation and has no room to say so: %s", message)

    return output

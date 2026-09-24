"""
A trial: a resolved cell run on a case (new-datamodel.md §5).

It is sent through pydantic-ai on vLLM (data-generation.md §2.4), with a
profile taken from the model's facts instead of one matched on its served
name, and with every field resolution wrote. The exact request body is kept:
the request, not the variations' names, says what ran.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

import httpx2
from jsonschema.validators import validator_for
from pydantic import JsonValue
from pydantic_ai import (
    Agent,
    AgentRunEvents,
    ModelSettings,
    NativeOutput,
    PromptedOutput,
    StructuredDict,
    ToolOutput,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import DEFAULT_PROFILE, ModelProfile, merge_profile
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.vllm import VLLMProvider

from chatddx.runtime.resolution import Resolution

# The request fields pydantic-ai's settings type, by the setting's name. The
# rest go in `extra_body`, which the openai SDK merges into the top of the
# request body.
SETTINGS = {
    "temperature": "temperature",
    "top_p": "top_p",
    "max_tokens": "max_tokens",
    "presence_penalty": "presence_penalty",
    "frequency_penalty": "frequency_penalty",
    "stop": "stop_sequences",
}

# What pydantic-ai would otherwise do to a request on its own account, and
# chatddx doesn't. The schema goes out as it was written, and it reaches the
# model only through the coercion's schema prompt or the final-result tool
# (data-generation.md §2.2): chatddx owns every string the model reads.
OWN: OpenAIModelProfile = {
    "json_schema_transformer": None,
    "native_output_requires_schema_in_instructions": False,
    # prompted is the schema shown and nothing more: no JSON mode
    "supports_json_object_output": False,
    # a model taken for a reasoning one would have its sampling dropped
    "openai_supports_reasoning": False,
}

# the tool a structured answer is given through, in tool mode
FINAL_RESULT = "final_result"


class Trial:
    def __init__(
        self,
        resolution: Resolution,
        case: str,
        api_key: str | None = None,
        transport: httpx2.AsyncBaseTransport | None = None,
        seed: int | None = None,
    ):
        self.resolution: Resolution = resolution
        self.case: str = case
        self.api_key: str | None = api_key
        self.transport: httpx2.AsyncBaseTransport | None = transport
        # the trial's own, not the configuration's (new-datamodel.md §2)
        self.seed: int | None = seed
        # the request body as it was sent
        self.request: bytes | None = None

    @asynccontextmanager
    async def stream(self) -> AsyncGenerator[AgentRunEvents[Any]]:
        system, user = self.resolution.render(self.case)

        async with httpx2.AsyncClient(
            transport=self.transport,
            event_hooks={"request": [self._keep]},
        ) as client:
            provider = VLLMProvider(
                base_url=self.resolution.endpoint,
                api_key=self.api_key,
                http_client=client,
            )
            model = OpenAIChatModel(
                self.resolution.served_name,
                provider=provider,
                profile=self._profile,
            )
            # One trial is one request: an answer that doesn't hold is
            # recorded, not repaired by asking again (data-generation.md §2.2).
            agent = Agent(
                model,
                instructions=system or None,
                output_type=self._output_type(),
                retries={"output": 0},
            )

            async with agent.run_stream_events(
                user, model_settings=self.settings()
            ) as events:
                yield events

    def settings(self) -> ModelSettings:
        settings: dict[str, Any] = {}
        extra_body: dict[str, JsonValue] = {}

        for name, value in self.resolution.fields.items():
            if name in SETTINGS:
                settings[SETTINGS[name]] = value
            else:
                extra_body[name] = value

        if extra_body:
            settings["extra_body"] = extra_body

        if self.seed is not None:
            settings["seed"] = self.seed

        return cast(ModelSettings, cast(object, settings))

    def _output_type(self) -> Any:
        coercion = self.resolution.coercion

        if coercion is None:
            return str

        # Its references inlined already, pydantic-ai has nothing to make of
        # it but a sort of its keywords; its properties stay in the order
        # they were written, the order a constrained decoder emits them in.
        structured = StructuredDict(coercion.sent)

        match coercion.mode:
            case "native":
                return NativeOutput(structured, template=False)
            case "tool":
                return ToolOutput(
                    structured,
                    name=FINAL_RESULT,
                    description=coercion.tool_description,
                )
            case "prompted":
                return PromptedOutput(structured, template=False)

    def _profile(self, _matched: ModelProfile) -> ModelProfile:
        # vLLM's profile for no model family in particular, and the facts'
        # overrides: nothing hangs on the served name
        return merge_profile(
            DEFAULT_PROFILE,
            VLLMProvider.model_profile(""),
            cast(ModelProfile, cast(object, self.resolution.profile)),
            OWN,
        )

    async def _keep(self, request: httpx2.Request) -> None:
        self.request = request.content


def invalid(schema: dict[str, JsonValue], answer: Any) -> str | None:
    """Why `answer` doesn't hold to `schema`, or None when it does."""
    validator = validator_for(schema)(schema)
    error = next(iter(validator.iter_errors(answer)), None)

    return None if error is None else f"{error.json_path}: {error.message}"

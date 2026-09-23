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
from pydantic import JsonValue
from pydantic_ai import Agent, AgentRunEvents, ModelSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import DEFAULT_PROFILE, ModelProfile, merge_profile
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


class Trial:
    def __init__(
        self,
        resolution: Resolution,
        case: str,
        api_key: str | None = None,
        transport: httpx2.AsyncBaseTransport | None = None,
    ):
        self.resolution: Resolution = resolution
        self.case: str = case
        self.api_key: str | None = api_key
        self.transport: httpx2.AsyncBaseTransport | None = transport
        # the request body as it was sent
        self.request: bytes | None = None

    @asynccontextmanager
    async def stream(self) -> AsyncGenerator[AgentRunEvents[str]]:
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
            agent = Agent(model, instructions=system or None, output_type=str)

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

        return cast(ModelSettings, cast(object, settings))

    def _profile(self, _matched: ModelProfile) -> ModelProfile:
        # vLLM's profile for no model family in particular, and the facts'
        # overrides: nothing hangs on the served name
        return merge_profile(
            DEFAULT_PROFILE,
            VLLMProvider.model_profile(""),
            cast(ModelProfile, cast(object, self.resolution.profile)),
        )

    async def _keep(self, request: httpx2.Request) -> None:
        self.request = request.content

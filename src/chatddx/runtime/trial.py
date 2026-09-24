"""
A trial: a resolved cell run on a case (new-datamodel.md §5).

It is sent through pydantic-ai on vLLM (data-generation.md §2.4), with a
profile taken from the model's facts instead of one matched on its served
name, and with every field resolution wrote. chatddx owns every string the
model reads (data-generation.md §2.2): the schema goes out as it was written,
pydantic-ai adds no words of its own, and an answer that doesn't hold is
recorded, not repaired by asking again. The exact bodies are kept, each
request as it went and each response as it came: the request, not the
variations' names, says what ran. So are pydantic-ai's messages, as far as
the run got.
"""

import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Any, cast, override

import httpx2
from jsonschema.validators import validator_for
from pydantic import JsonValue, ValidationError
from pydantic_ai import (
    Agent,
    AgentRunEvents,
    ModelMessage,
    ModelSettings,
    NativeOutput,
    PromptedOutput,
    StructuredDict,
    Tool,
    ToolOutput,
    UsageLimits,
    capture_run_messages,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import DEFAULT_PROFILE, ModelProfile, merge_profile
from pydantic_ai.profiles.openai import OpenAIModelProfile
from pydantic_ai.providers.vllm import VLLMProvider

from chatddx.runtime.implementation import Implementation, implementation
from chatddx.runtime.resolution import Resolution

SETTINGS = {
    "temperature": "temperature",
    "top_p": "top_p",
    "max_tokens": "max_tokens",
    "presence_penalty": "presence_penalty",
    "frequency_penalty": "frequency_penalty",
    "stop": "stop_sequences",
}

OWN: OpenAIModelProfile = {
    "json_schema_transformer": None,
    "native_output_requires_schema_in_instructions": False,
    "supports_json_object_output": False,
    "openai_supports_reasoning": False,
}

FINAL_RESULT = "final_result"

TOOL_ROUNDS = 5


class Trial:
    def __init__(
        self,
        resolution: Resolution,
        case: str,
        api_key: str | None = None,
        transport: httpx2.AsyncBaseTransport | None = None,
        seed: int | None = None,
        implementations: dict[str, str] | None = None,
        run_id: str | None = None,
        conversation_id: str | None = None,
        history: Sequence[ModelMessage] = (),
    ):
        self.resolution: Resolution = resolution
        self.case: str = case
        self.api_key: str | None = api_key
        self.transport: httpx2.AsyncBaseTransport | None = transport
        self.seed: int | None = seed
        self.run_id: str = run_id or str(uuid.uuid4())
        self.conversation_id: str = conversation_id or str(uuid.uuid4())
        self.requests: list[bytes] = []
        self.responses: list[bytearray] = []
        self.messages: list[ModelMessage] = []
        self.history: list[ModelMessage] = list(history)
        self.implementations: dict[str, Implementation] = {}

        for tool in resolution.tools:
            entry_point = (implementations or {}).get(tool.name)

            if entry_point is None:
                raise ValueError(f"the tool '{tool.name}' has nothing to run")

            try:
                self.implementations[tool.name] = implementation(entry_point)
            except ValueError as e:
                raise ValueError(f"the tool '{tool.name}' can't run: {e}") from None

    @asynccontextmanager
    async def stream(self) -> AsyncGenerator[AgentRunEvents[Any]]:
        system, user = self.resolution.render(self.case)

        async with httpx2.AsyncClient(
            transport=self.transport,
            event_hooks={"request": [self._sent], "response": [self._received]},
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
            agent = Agent(
                model,
                instructions=system or None,
                output_type=self._output_type(),
                tools=self._tools(),
                retries={"output": 0, "tools": 0},
            )

            with capture_run_messages() as messages:
                self.messages = messages

                async with agent.run_stream_events(
                    user,
                    model_settings=self.settings(),
                    usage_limits=UsageLimits(request_limit=TOOL_ROUNDS + 1),
                    run_id=self.run_id,
                    conversation_id=self.conversation_id,
                    message_history=self.history or None,
                ) as events:
                    yield events

    @property
    def new_messages(self) -> list[ModelMessage]:
        """The messages the run added to the conversation it continued."""
        return self.messages[len(self.history) :]

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

    def _tools(self) -> list[Tool[Any]]:
        return [
            Tool.from_schema(
                _runner(self.implementations[tool.name], tool.parameters),
                name=tool.name,
                description=tool.description,
                json_schema=tool.parameters,
            )
            for tool in self.resolution.tools
        ]

    def _output_type(self) -> Any:
        coercion = self.resolution.coercion

        if coercion is None:
            return str

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
        return merge_profile(
            DEFAULT_PROFILE,
            VLLMProvider.model_profile(""),
            cast(ModelProfile, cast(object, self.resolution.profile)),
            OWN,
        )

    async def _sent(self, request: httpx2.Request) -> None:
        self.requests.append(request.content)

    async def _received(self, response: httpx2.Response) -> None:
        body = bytearray()
        self.responses.append(body)

        try:
            body.extend(response.content)
        except httpx2.ResponseNotRead:
            stream = cast(httpx2.AsyncByteStream, response.stream)
            response.stream = _Copied(stream, body)


class _Copied(httpx2.AsyncByteStream):
    """A response's body, copied into `into` as it is read."""

    def __init__(self, stream: httpx2.AsyncByteStream, into: bytearray):
        self._stream: httpx2.AsyncByteStream = stream
        self._into: bytearray = into

    @override
    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self._stream:
            self._into.extend(chunk)
            yield chunk

    @override
    async def aclose(self) -> None:
        await self._stream.aclose()


def _runner(
    implementation: Implementation, parameters: dict[str, JsonValue]
) -> Callable[..., Any]:
    """
    A tool's function, called with arguments that hold to its parameters;
    what doesn't hold, or fails, goes back to the model as what it returned.
    """

    def run(**arguments: Any) -> Any:
        problem = invalid(parameters, arguments)

        if problem is not None:
            return f"invalid arguments: {problem}"

        try:
            return implementation.function(**arguments)
        except Exception as e:  # noqa: BLE001
            return f"{type(e).__name__}: {e}"

    return run


def cause_of(error: Exception) -> str:
    """What went wrong beneath pydantic-ai's own message: the first validation error."""
    cause = error.__cause__

    while cause is not None and not isinstance(cause, ValidationError):
        cause = cause.__cause__

    if not isinstance(cause, ValidationError):
        return str(error)

    first = cause.errors(include_url=False, include_input=False)[0]
    where = ".".join(str(part) for part in first["loc"])

    return f"{where}: {first['msg']}" if where else first["msg"]


def invalid(schema: dict[str, JsonValue], answer: Any) -> str | None:
    """Why `answer` doesn't hold to `schema`, or None when it does."""
    validator = validator_for(schema)(schema)
    error = next(iter(validator.iter_errors(answer)), None)

    return None if error is None else f"{error.json_path}: {error.message}"

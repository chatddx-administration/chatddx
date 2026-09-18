# src/chatddx/runtime/runners.py
import uuid
from collections.abc import AsyncGenerator

from django.utils import timezone
from pydantic_ai import (
    AgentRunResult,
    AgentRunResultEvent,
    AgentStreamEvent,
    ModelRequest,
    ModelResponse,
    UnexpectedModelBehavior,
)
from pydantic_core import to_jsonable_python

from chatddx.core.choices import RoleChoices
from chatddx.history.models import MessageModel
from chatddx.history.schemas import SessionSpec
from chatddx.repo.entities.agent.pydantic import AgentTrailSpec
from chatddx.runtime.context import AgentContext, OutputType
from chatddx.utils import Dispatcher

from .builder import (
    build_agent,
    build_output_type,
)


async def run_from_spec(
    agent_spec: AgentTrailSpec,
    prompt: str,
    dispatcher: Dispatcher | None = None,
) -> AgentRunResult[OutputType]:

    if not dispatcher:
        dispatcher = Dispatcher()

    output_type = build_output_type(agent_spec)
    agent = build_agent(agent_spec, output_type)
    agent_context = AgentContext(agent=agent_spec, output_type=output_type)

    result = await agent.run(prompt, deps=agent_context)

    await dispatcher.publish(result)

    return result


async def stream_from_session(
    session: SessionSpec,
    prompt: str,
    dispatcher: Dispatcher | None = None,
    agent_spec: AgentTrailSpec | None = None,
) -> AsyncGenerator[AgentStreamEvent | AgentRunResultEvent[OutputType], None]:

    if not dispatcher:
        dispatcher = Dispatcher()

    if not agent_spec:
        agent_spec = session.default_agent.target

    _ = dispatcher.subscribe(
        on_result(
            session.id,
            agent_spec.id,
        )
    )

    output_type = build_output_type(agent_spec)

    agent_context = AgentContext(
        agent=agent_spec,
        output_type=output_type,
        session=session,
    )

    agent = build_agent(
        agent_spec,
        output_type,
    )

    _ = dispatcher.subscribe(
        on_error(
            session.id,
            agent_spec.id,
        )
    )

    try:
        async with agent.run_stream_events(
            prompt,
            deps=agent_context,
            message_history=get_message_history(session),
        ) as events:
            async for event in events:
                yield event

            await dispatcher.publish(events.result)

    except Exception as e:
        _ = await publish_error(dispatcher, e)
        raise


def get_message_history(session: SessionSpec):
    return [
        m.payload
        for m in session.messages
        if isinstance(m.payload, (ModelResponse, ModelRequest))
    ]


async def run_from_session(
    session: SessionSpec,
    prompt: str,
    dispatcher: Dispatcher | None = None,
    agent_spec: AgentTrailSpec | None = None,
    api_key: str | None = None,
) -> AgentRunResult[OutputType]:

    if not dispatcher:
        dispatcher = Dispatcher()

    if not agent_spec:
        agent_spec = session.default_agent.target

    _ = dispatcher.subscribe(
        on_result(
            session.id,
            agent_spec.id,
        )
    )
    _ = dispatcher.subscribe(
        on_prompt(
            session.id,
            agent_spec.id,
        )
    )
    _ = dispatcher.subscribe(
        on_error(
            session.id,
            agent_spec.id,
        )
    )

    await dispatcher.publish(prompt)

    output_type = build_output_type(agent_spec)

    agent = build_agent(
        agent_spec=agent_spec,
        output_type=output_type,
        api_key=api_key,
    )

    agent_context = AgentContext(
        agent=agent_spec,
        output_type=output_type,
        session=session,
    )

    try:
        result = await agent.run(
            prompt,
            deps=agent_context,
            message_history=get_message_history(session),
        )

        await dispatcher.publish(result)
        return result

    except Exception as e:
        await publish_error(dispatcher, e)
        raise


async def publish_error(dispatcher: Dispatcher, error: Exception) -> None:
    if isinstance(error, UnexpectedModelBehavior):
        root_cause = error.__cause__

        log_payload = {
            "type": "llm_model_error",
            "message": str(error),
            "root_cause_type": type(root_cause).__name__ if root_cause else None,
            "root_cause_detail": str(root_cause) if root_cause else None,
        }

        await dispatcher.publish(log_payload)
    else:
        await dispatcher.publish(error)


def on_prompt(session_id: int, agent_id: int):
    async def _on_prompt(prompt: str):
        _ = await MessageModel.objects.acreate(
            agent_id=agent_id,
            session_id=session_id,
            kind="prompt",
            run_id=uuid.UUID(int=0),
            role=RoleChoices.USER,
            payload={"content": prompt},
            timestamp=timezone.now(),
        )

    return _on_prompt


def on_error(session_id: int, agent_id: int):
    async def _on_error(error: Exception):
        error_message = f"Agent execution failed: {type(error).__name__} - {error}"

        _ = await MessageModel.objects.acreate(
            agent_id=agent_id,
            session_id=session_id,
            kind="error",
            run_id=uuid.UUID(int=0),
            role=RoleChoices.SYSTEM,
            payload={"error_type": type(error).__name__, "content": error_message},
            timestamp=timezone.now(),
        )

    return _on_error


def on_result(session_id: int, agent_id: int):
    async def _on_result(result: AgentRunResult):
        messages = result.new_messages()
        messages_to_create: list[MessageModel] = []

        for msg in messages:
            role = infer_role(msg)

            messages_to_create.append(
                MessageModel(
                    agent_id=agent_id,
                    session_id=session_id,
                    kind=msg.kind,
                    run_id=result.run_id,
                    role=role,
                    payload=to_jsonable_python(msg),
                    timestamp=msg.timestamp,
                )
            )

        if messages_to_create:
            _ = await MessageModel.objects.abulk_create(messages_to_create)

    return _on_result


def infer_role(msg: ModelResponse | ModelRequest) -> str:
    if isinstance(msg, ModelResponse):
        return RoleChoices.ASSISTANT

    if isinstance(msg, ModelRequest):
        part_kinds = {part.part_kind for part in msg.parts}

        if "system-prompt" in part_kinds:
            return RoleChoices.SYSTEM
        if "tool-return" in part_kinds or "retry-prompt" in part_kinds:
            return RoleChoices.TOOL

        return RoleChoices.USER
    return RoleChoices.UNKNOWN

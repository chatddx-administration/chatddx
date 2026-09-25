# pyright: basic
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from django.db import transaction
from pydantic import JsonValue
from pydantic_ai import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    ToolReturnPart,
    UserPromptPart,
)

from chatddx.core.models import IdentityModel
from chatddx.history.models import (
    ConversationContext,
    ConversationModel,
    MessageKind,
    MessageModel,
    Role,
    RunModel,
    RunStatus,
    RunToolBranchModel,
    TrialModel,
)
from chatddx.repo.entities.client.django import ClientTrailModel
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailIn
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.store.trail import dump_trail
from chatddx.runtime.client import Client, running
from chatddx.runtime.run import Run


@dataclass(frozen=True)
class Branches:
    stack: int
    llm: int | None
    tools: dict[int, str] = field(default_factory=dict[int, str])


@dataclass(frozen=True)
class Outcome:
    status: RunStatus
    answer: JsonValue = None
    valid: bool | None = None
    error: str | None = None


def record(
    owner: str,
    configuration: ConfigurationTrailIn,
    branches: Branches,
    case: int,
    run: Run,
    outcome: Outcome,
    started: datetime,
    finished: datetime,
    description: str | None = None,
    context: ConversationContext = ConversationContext.REPL,
    conversation: ConversationModel | None = None,
    client: Client | None = None,
) -> RunModel:
    client = client or running()

    with transaction.atomic():
        identity = IdentityModel.objects.get(name=owner)
        stack = StackBranchModel.objects.get(pk=branches.stack)
        trial_model = _trial(configuration, stack.trail_id, case, run.seed)

        conversation = conversation or ConversationModel.objects.create(
            uuid=UUID(run.conversation_id),
            owner=identity,
            context=context,
            description=description[:255] if description else None,
        )
        _ = MessageModel.objects.bulk_create(
            _messages(conversation, run, outcome.error, finished)
        )

        recorded = RunModel.objects.create(
            uuid=UUID(run.run_id),
            owner=identity,
            trial=trial_model,
            conversation=conversation,
            status=outcome.status,
            stack_branch=stack,
            llm_branch_id=branches.llm,
            client=dump_trail(ClientTrailModel, client.trail),
            client_rev=client.rev,
            client_packages=client.packages,
            started=started,
            finished=finished,
            requests=[body.decode() for body in run.requests],
            responses=[bytes(body).decode() for body in run.responses],
            answer=outcome.answer,
            valid=outcome.valid,
            finish_reason=_finish_reason(run.new_messages),
            error=outcome.error,
        )
        _ = RunToolBranchModel.objects.bulk_create(
            RunToolBranchModel(run=recorded, tool_branch_id=tool, blob=blob)
            for tool, blob in branches.tools.items()
        )

    return recorded


def _trial(
    configuration: ConfigurationTrailIn,
    stack: int,
    case: int,
    seed: int | None,
) -> TrialModel:
    """The trial of the cell on the case with the seed: the one run before, or a new one."""
    trial, _ = TrialModel.objects.get_or_create(
        configuration=dump_trail(ConfigurationTrailModel, configuration),
        stack_id=stack,
        case_id=case,
        seed=seed,
    )

    return trial


def _messages(
    conversation: ConversationModel,
    run: Run,
    error: str | None,
    at: datetime,
) -> list[MessageModel]:
    payloads = ModelMessagesTypeAdapter.dump_python(run.new_messages, mode="json")
    messages = [
        MessageModel(
            conversation=conversation,
            run_uuid=UUID(run.run_id),
            role=_role(message),
            kind=message.kind,
            payload=payload,
            timestamp=message.timestamp or at,
        )
        for message, payload in zip(run.new_messages, payloads, strict=True)
    ]

    if error is not None:
        messages.append(
            MessageModel(
                conversation=conversation,
                run_uuid=UUID(run.run_id),
                role=Role.UNKNOWN,
                kind=MessageKind.ERROR,
                payload={"error": error},
                timestamp=at,
            )
        )

    return messages


def _role(message: ModelMessage) -> Role:
    match message:
        case ModelResponse():
            return Role.ASSISTANT
        case ModelRequest(parts=parts):
            kinds = {type(part) for part in parts}

            if UserPromptPart in kinds:
                return Role.USER
            if kinds & {ToolReturnPart, RetryPromptPart}:
                return Role.TOOL
            if SystemPromptPart in kinds:
                return Role.SYSTEM

    return Role.UNKNOWN


def _finish_reason(messages: list[ModelMessage]) -> str | None:
    """The last response's: a truncated answer is not a wrong one."""
    responses = [m for m in messages if isinstance(m, ModelResponse)]
    return responses[-1].finish_reason if responses else None

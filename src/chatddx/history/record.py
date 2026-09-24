# pyright: basic
"""
Writing a run down: the trial it was a go at, found or made, the run with
what came of it, and the session its messages were exchanged in.

Every run is written down, whatever came of it: an answer, one that doesn't
hold, none, or an error on the way. A run of the same cell on the same case
with the same seed is another run of the same trial.
"""

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
    MessageKind,
    MessageModel,
    Role,
    RunModel,
    RunStatus,
    RunToolBranchModel,
    SessionContext,
    SessionModel,
    TrialModel,
)
from chatddx.repo.entities.client.django import ClientTrailModel
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailSchema
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.shufflers.trail import dump_trail
from chatddx.runtime.client import Client, running
from chatddx.runtime.trial import Trial


@dataclass(frozen=True)
class Branches:
    """The branch rows whose details resolution read, by their ids."""

    stack: int
    model: int | None
    tools: list[int] = field(default_factory=list[int])


@dataclass(frozen=True)
class Outcome:
    """What came of a run."""

    status: RunStatus
    output: JsonValue = None
    valid: bool | None = None
    error: str | None = None


def record(
    owner: str,
    configuration: ConfigurationTrailSchema,
    branches: Branches,
    case: int,
    trial: Trial,
    outcome: Outcome,
    started: datetime,
    finished: datetime,
    description: str | None = None,
    context: SessionContext = SessionContext.REPL,
    session: SessionModel | None = None,
    client: Client | None = None,
) -> RunModel:
    """
    Write down a run of `trial`, a cell run on the case trail `case`: the
    configuration it ran, as content, and the branches of the stack, model
    and tools it read, and the client it ran on: the one running, unless
    another is given. A run that continued `session` adds to it.
    """
    client = client or running()

    with transaction.atomic():
        identity = IdentityModel.objects.get(name=owner)
        stack = StackBranchModel.objects.get(pk=branches.stack)
        trial_model = _trial(identity, configuration, stack.target_id, case, trial.seed)

        session = session or SessionModel.objects.create(
            uuid=UUID(trial.conversation_id),
            owner=identity,
            context=context,
            description=description[:255] if description else None,
        )
        _ = MessageModel.objects.bulk_create(
            _messages(session, trial, outcome.error, finished)
        )

        run = RunModel.objects.create(
            uuid=UUID(trial.run_id),
            owner=identity,
            trial=trial_model,
            session=session,
            status=outcome.status,
            stack_branch=stack,
            model_branch_id=branches.model,
            client=dump_trail(ClientTrailModel, client.trail),
            client_rev=client.rev,
            client_packages=client.packages,
            started=started,
            finished=finished,
            requests=[body.decode() for body in trial.requests],
            responses=[bytes(body).decode() for body in trial.responses],
            output=outcome.output,
            valid=outcome.valid,
            finish_reason=_finish_reason(trial.new_messages),
            error=outcome.error,
        )
        _ = RunToolBranchModel.objects.bulk_create(
            RunToolBranchModel(run=run, tool_branch_id=tool) for tool in branches.tools
        )

    return run


def _trial(
    owner: IdentityModel,
    configuration: ConfigurationTrailSchema,
    stack: int,
    case: int,
    seed: int | None,
) -> TrialModel:
    """The owner's trial of the cell on the case: the one run before, or a new one."""
    fields = {
        "owner": owner,
        "configuration": dump_trail(ConfigurationTrailModel, configuration),
        "stack_id": stack,
        "case_id": case,
        "seed": seed,
    }
    found = TrialModel.objects.filter(**fields).order_by("timestamp", "pk").first()

    return found or TrialModel.objects.create(**fields)


def _messages(
    session: SessionModel,
    trial: Trial,
    error: str | None,
    at: datetime,
) -> list[MessageModel]:
    payloads = ModelMessagesTypeAdapter.dump_python(trial.new_messages, mode="json")
    messages = [
        MessageModel(
            session=session,
            run_id=UUID(trial.run_id),
            role=_role(message),
            kind=message.kind,
            payload=payload,
            timestamp=message.timestamp or at,
        )
        for message, payload in zip(trial.new_messages, payloads, strict=True)
    ]

    if error is not None:
        messages.append(
            MessageModel(
                session=session,
                run_id=UUID(trial.run_id),
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

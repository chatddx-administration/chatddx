# pyright: basic
"""
History: what ran, and what came of it.

A trial is one cell on one case, with its seed: a configuration and a stack,
by their trails, and the case (new-datamodel.md §6). A run is one go at a
trial, one pydantic-ai agent run, whose id it takes. It keeps what resolution
read, the exact bytes it sent and got back, and what came of them. Its
session holds the exchange as pydantic-ai's messages. A trial can be run
again, to see a seed hold or to retry one that errored, and each run keeps
its own record.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from django.contrib.postgres.fields import ArrayField
from django.db.models import (
    CASCADE,
    PROTECT,
    BigIntegerField,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    JSONField,
    ManyToManyField,
    Model,
    QuerySet,
    TextField,
    UUIDField,
)

from chatddx.core.models import IdentityModel
from chatddx.repo.entities.case.django import CaseTrailModel
from chatddx.repo.entities.client.django import ClientTrailModel
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.model.django import ModelBranchModel
from chatddx.repo.entities.stack.django import StackBranchModel, StackTrailModel
from chatddx.repo.entities.tool.django import ToolBranchModel
from chatddx.repo.families.django import OrderedJSONField

__all__ = [
    "MessageModel",
    "RunModel",
    "RunToolBranchModel",
    "SessionModel",
    "TrialModel",
]


class RunStatus(StrEnum):
    STORED = "stored"
    QUEUED = "queued"
    RUNNING = "running"
    ERRORED = "errored"
    COMPLETED = "completed"
    SCORED = "scored"


class SessionContext(StrEnum):
    """Where a session was held."""

    CHAT = "chat"
    REPL = "repl"
    WORKER = "worker"


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    UNKNOWN = "unknown"


class MessageKind(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"


class TrialModel(Model):
    class Meta:
        app_label = "orm"

    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    timestamp = DateTimeField(auto_now_add=True)
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    owner_id: int
    collaborators: ManyToManyField[IdentityModel, Any] = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_trials",
    )

    configuration = ForeignKey(
        ConfigurationTrailModel,
        on_delete=PROTECT,
        related_name="trials",
    )
    configuration_id: int
    stack = ForeignKey(
        StackTrailModel,
        on_delete=PROTECT,
        related_name="trials",
    )
    stack_id: int
    case = ForeignKey(
        CaseTrailModel,
        on_delete=PROTECT,
        related_name="trials",
    )
    case_id: int
    # the trial's, not the configuration's (new-datamodel.md §6)
    seed = BigIntegerField(
        null=True,
        blank=True,
        default=None,
    )

    runs: QuerySet[RunModel]


class SessionModel(Model):
    class Meta:
        app_label = "orm"

    # pydantic-ai's conversation id for the runs held in it
    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    description = CharField(
        max_length=255,
        null=True,
        default=None,
        blank=True,
    )
    timestamp = DateTimeField(auto_now_add=True)
    context = CharField(max_length=16)
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    owner_id: int
    collaborators: ManyToManyField[IdentityModel, Any] = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_sessions",
    )

    messages: QuerySet[MessageModel]
    runs: QuerySet[RunModel]


class RunModel(Model):
    class Meta:
        app_label = "orm"

    # pydantic-ai's id for the agent run, which its messages carry
    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    timestamp = DateTimeField(auto_now_add=True)
    status = CharField(
        max_length=16,
        default=RunStatus.STORED.value,
    )
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    owner_id: int
    collaborators: ManyToManyField[IdentityModel, Any] = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_runs",
    )

    trial = ForeignKey(
        TrialModel,
        on_delete=PROTECT,
        related_name="runs",
    )
    trial_id: int
    session = ForeignKey(
        SessionModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="runs",
    )
    session_id: int | None

    # The branch rows whose details resolution read (new-datamodel.md §1):
    # the stack's endpoint and served name, the model's facts, and what each
    # tool runs.
    stack_branch = ForeignKey(
        StackBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="runs",
    )
    stack_branch_id: int | None
    model_branch = ForeignKey(
        ModelBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="runs",
    )
    model_branch_id: int | None
    tool_branches: ManyToManyField[ToolBranchModel, Any] = ManyToManyField(
        ToolBranchModel,
        through="RunToolBranchModel",
        blank=True,
        related_name="runs",
    )

    client = ForeignKey(
        ClientTrailModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="runs",
    )
    client_id: int | None
    client_rev = CharField(
        max_length=64,
        default=None,
        null=True,
        blank=True,
    )
    client_packages: JSONField[dict[str, str]] = JSONField(
        default=dict,
        blank=True,
    )

    started = DateTimeField(
        default=None,
        null=True,
        blank=True,
    )
    finished = DateTimeField(
        default=None,
        null=True,
        blank=True,
    )

    # the bodies as they went and came, one of each per request
    # (data-generation.md §3.3)
    requests = ArrayField(
        TextField(),
        default=list,
        blank=True,
    )
    responses = ArrayField(
        TextField(),
        default=list,
        blank=True,
    )

    # The answer with its envelope removed, the same whichever mode carried
    # it (new-datamodel.md §4), in the order the model wrote it.
    output = OrderedJSONField(
        default=None,
        null=True,
        blank=True,
    )
    # whether the output holds to the output's schema; None for free text
    valid = BooleanField(
        default=None,
        null=True,
        blank=True,
    )
    # the last response's: a truncated answer is not a wrong one
    finish_reason = CharField(
        max_length=32,
        default=None,
        null=True,
        blank=True,
    )
    # why the run came to no output, or errored
    error = TextField(
        default=None,
        null=True,
        blank=True,
    )


class RunToolBranchModel(Model):
    """A tool's branch a run read: kept as long as the run is."""

    class Meta:
        app_label = "orm"

    run = ForeignKey(
        RunModel,
        on_delete=CASCADE,
    )
    tool_branch = ForeignKey(
        ToolBranchModel,
        on_delete=PROTECT,
    )


class MessageModel(Model):
    class Meta:
        app_label = "orm"
        ordering = ("pk",)

    session = ForeignKey(
        SessionModel,
        related_name="messages",
        on_delete=PROTECT,
    )
    session_id: int
    # the agent run that made it: a run's uuid
    run_id = UUIDField(db_index=True)
    role = CharField(max_length=16)
    kind = CharField(max_length=16)
    # pydantic-ai's message, as it serializes it; an error's type and text
    payload: JSONField[dict[str, Any]] = JSONField()
    timestamp = DateTimeField()

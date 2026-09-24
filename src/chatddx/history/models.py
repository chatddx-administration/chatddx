# pyright: basic
"""
History: what ran, and what came of it.

A trial is one cell on one case, with its seed: a configuration and a stack,
by their trails, and the case (new-datamodel.md §6). It is content, like a
trail, and belongs to no one: runs of the same four are runs of one trial,
whoever made them. A run is one go at a trial, one pydantic-ai agent run,
whose id it takes, and it is its maker's. It keeps what resolution read, the
exact bytes it sent and got back, and what came of them. Its conversation
holds the exchange as pydantic-ai's messages. A trial can be run again, to see a
seed hold or to retry one that errored, and each run keeps its own record.
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
    FloatField,
    ForeignKey,
    JSONField,
    ManyToManyField,
    Model,
    QuerySet,
    TextField,
    UniqueConstraint,
    UUIDField,
)

from chatddx.core.models import IdentityModel
from chatddx.repo.entities.case.django import CaseBranchModel, CaseTrailModel
from chatddx.repo.entities.client.django import ClientTrailModel
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.llm.django import LLMBranchModel
from chatddx.repo.entities.scorer.django import ScorerTrailModel
from chatddx.repo.entities.stack.django import StackBranchModel, StackTrailModel
from chatddx.repo.entities.tool.django import ToolBranchModel
from chatddx.repo.families.django import OrderedJSONField

__all__ = [
    "ConversationModel",
    "MessageModel",
    "RunModel",
    "RunToolBranchModel",
    "ScoreModel",
    "TrialModel",
]


class RunStatus(StrEnum):
    ERRORED = "errored"
    COMPLETED = "completed"


class ConversationContext(StrEnum):
    """Where a conversation was held."""

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
        db_table = "history_trial"
        constraints = (
            UniqueConstraint(
                fields=("configuration", "stack", "case", "seed"),
                nulls_distinct=False,
                name="one_trial_per_cell_case_and_seed",
            ),
        )

    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    timestamp = DateTimeField(auto_now_add=True)

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
    seed = BigIntegerField(
        null=True,
        blank=True,
        default=None,
    )

    runs: QuerySet[RunModel]


class ConversationModel(Model):
    class Meta:
        db_table = "history_conversation"

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
        related_name="shared_conversations",
    )

    messages: QuerySet[MessageModel]
    runs: QuerySet[RunModel]


class RunModel(Model):
    class Meta:
        db_table = "history_run"

    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    timestamp = DateTimeField(auto_now_add=True)
    status = CharField(max_length=16)
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
    conversation = ForeignKey(
        ConversationModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="runs",
    )
    conversation_id: int | None

    stack_branch = ForeignKey(
        StackBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="runs",
    )
    stack_branch_id: int | None
    llm_branch = ForeignKey(
        LLMBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="runs",
    )
    llm_branch_id: int | None
    scores: QuerySet[ScoreModel]
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

    answer = OrderedJSONField(
        default=None,
        null=True,
        blank=True,
    )
    valid = BooleanField(
        default=None,
        null=True,
        blank=True,
    )
    finish_reason = CharField(
        max_length=32,
        default=None,
        null=True,
        blank=True,
    )
    error = TextField(
        default=None,
        null=True,
        blank=True,
    )


class RunToolBranchModel(Model):
    """
    A tool's branch a run read, kept as long as the run is, and the git blob
    id of the file that ran for it (`chatddx.runtime.implementation`).
    """

    class Meta:
        db_table = "history_run_tool_branch"

    run = ForeignKey(
        RunModel,
        on_delete=CASCADE,
    )
    tool_branch = ForeignKey(
        ToolBranchModel,
        on_delete=PROTECT,
    )
    blob = CharField(max_length=64)


class ScoreModel(Model):
    """
    What a scorer made of a run: its value, what in the answer it rests on,
    or why there is none; and what it was made with: the scorer, by its trail
    and by the name it had for whoever scored, the case branch whose targets
    were read, the target the view was held to, and the git blob id of the
    scorer's file. A run scored again, after any of them changed, keeps each
    score.
    """

    class Meta:
        db_table = "history_score"
        ordering = ("pk",)

    run = ForeignKey(
        RunModel,
        related_name="scores",
        on_delete=CASCADE,
    )
    run_id: int
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    owner_id: int
    scorer = ForeignKey(
        ScorerTrailModel,
        on_delete=PROTECT,
        related_name="scores",
    )
    scorer_id: int
    scorer_name = CharField(max_length=255)
    # none for a scorer that needs no target
    case_branch = ForeignKey(
        CaseBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="scores",
    )
    case_branch_id: int | None
    # none where the case expects none, or the scorer needs none
    target = TextField(
        default=None,
        null=True,
        blank=True,
    )
    blob = CharField(max_length=64)
    value = FloatField(
        default=None,
        null=True,
        blank=True,
    )
    answer = TextField(
        default=None,
        null=True,
        blank=True,
    )
    reason = CharField(
        max_length=64,
        default=None,
        null=True,
        blank=True,
    )
    timestamp = DateTimeField(auto_now_add=True)


class MessageModel(Model):
    class Meta:
        db_table = "history_message"
        ordering = ("pk",)

    conversation = ForeignKey(
        ConversationModel,
        related_name="messages",
        on_delete=PROTECT,
    )
    conversation_id: int
    run_uuid = UUIDField(db_index=True)
    role = CharField(max_length=16)
    kind = CharField(max_length=16)
    payload: JSONField[dict[str, Any]] = JSONField()
    timestamp = DateTimeField()

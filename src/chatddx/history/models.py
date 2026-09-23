# pyright: basic
from __future__ import annotations

import uuid
from typing import Any

from django.db.models import (
    PROTECT,
    SET_DEFAULT,
    CharField,
    DateTimeField,
    ForeignKey,
    JSONField,
    ManyToManyField,
    Model,
    QuerySet,
    UUIDField,
)

from chatddx.core.choices import (
    MessageKindChoices,
    RoleChoices,
    RunStatusChoices,
    SessionContextChoices,
)
from chatddx.core.models import IdentityModel, TagModel
from chatddx.repo.entities.agent.django import AgentBranchModel, AgentTrailModel
from chatddx.repo.entities.case.django import CaseTrailModel
from chatddx.repo.entities.expect.django import ExpectTrailModel
from chatddx.repo.entities.scorer.django import ScorerBranchModel


class BatchModel(Model):
    """
    One standing order for experiments: an agent, the case tags to draw cases
    from, and the scorers to score them with.

    The order is kept, not its outcome, so the same batch can be generated
    from more than once (see `chatddx.history.batches`) and every experiment
    it ever made points back at it through `ExperimentModel.batch`.
    """

    class Meta:
        app_label = "orm"
        db_table = "agents_batch"

    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    timestamp = DateTimeField(auto_now_add=True)
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    owner_id: int

    agent = ForeignKey(
        AgentTrailModel,
        on_delete=PROTECT,
        related_name="batches",
    )
    agent_id: int

    case_tags = ManyToManyField(
        TagModel,
        related_name="batches",
    )

    # An empty set is not "no scorers" but "every scorer the cases carry";
    # see `chatddx.history.batches.plan`.
    scorers = ManyToManyField(
        ScorerBranchModel,
        blank=True,
        related_name="batches",
    )

    experiments: QuerySet[ExperimentModel]


class ExperimentModel(Model):
    class Meta:
        app_label = "orm"
        db_table = "agents_experiment"

    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    timestamp = DateTimeField(auto_now_add=True)
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    owner_id: int
    collaborators = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_experiments",
    )

    agent = ForeignKey(
        AgentTrailModel,
        on_delete=PROTECT,
        related_name="experiments",
    )
    agent_id: int
    case = ForeignKey(
        CaseTrailModel,
        on_delete=PROTECT,
        related_name="experiments",
    )
    case_id: int
    expect = ForeignKey(
        ExpectTrailModel,
        on_delete=PROTECT,
        related_name="experiments",
    )
    expect_id: int

    # The batch that generated this experiment, where one did: an experiment
    # added by hand has none.
    batch = ForeignKey(
        BatchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="experiments",
    )
    batch_id: int | None


class SessionModel(Model):
    class Meta:
        app_label = "orm"
        db_table = "agents_session"

    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    description = CharField(
        max_length=255,
        null=True,
        default=None,
        blank=True,
    )
    timestamp = DateTimeField(auto_now_add=True)
    context = CharField(
        max_length=255,
        choices=SessionContextChoices.choices,
    )
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    default_agent = ForeignKey(
        AgentBranchModel,
        default=None,
        null=True,
        on_delete=SET_DEFAULT,
    )
    collaborators = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_sessions",
    )

    messages: QuerySet[MessageModel]


class RunModel(Model):
    class Meta:
        app_label = "orm"
        db_table = "agents_run"

    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    timestamp = DateTimeField(auto_now_add=True)
    status = CharField(
        max_length=255,
        choices=RunStatusChoices.choices,
        default=RunStatusChoices.STORED,
    )
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    owner_id: int
    collaborators = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_runs",
    )

    experiment = ForeignKey(
        ExperimentModel,
        on_delete=PROTECT,
        related_name="runs",
    )
    experiment_id: int

    session = ForeignKey(
        SessionModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="runs",
    )
    session_id: int | None

    # What the agent returned: the value its output type's definition
    # describes, the same whichever coercion strategy got it out of the
    # model. It is what the run is scored on; `result` is what the scorer
    # made of it.
    output: JSONField[Any | None] = JSONField(
        default=None,
        null=True,
        blank=True,
    )

    result: JSONField[Any | None] = JSONField(
        default=None,
        null=True,
        blank=True,
    )


class MessageModel(Model):
    class Meta:
        app_label = "orm"
        db_table = "agents_message"
        ordering = ("pk",)

    role = CharField(max_length=255, choices=RoleChoices.choices)
    kind = CharField(max_length=255, choices=MessageKindChoices.choices)
    run_id = UUIDField(db_index=True)
    payload: JSONField[dict[str, Any]] = JSONField()
    timestamp = DateTimeField()

    agent = ForeignKey(
        AgentTrailModel,
        on_delete=PROTECT,
    )
    session = ForeignKey(
        SessionModel,
        related_name="messages",
        on_delete=PROTECT,
    )

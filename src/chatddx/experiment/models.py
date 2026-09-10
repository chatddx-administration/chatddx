# src/chatddx/experiment/models.py
from __future__ import annotations

import uuid
from typing import Any

from django.db.models import (
    PROTECT,
    CharField,
    DateTimeField,
    ForeignKey,
    JSONField,
    ManyToManyField,
    Model,
    UUIDField,
)

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.history.models import SessionModel
from chatddx.repo.trail_models import (
    AgentTrailModel,
    CaseTrailModel,
    ExpectTrailModel,
    ScorerTrailModel,
)


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

    tags = CharField(max_length=255, blank=True, default="")

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

    scorer = ForeignKey(
        ScorerTrailModel,
        on_delete=PROTECT,
        default=None,
        null=True,
        blank=True,
        related_name="experiments",
    )
    scorer_id: int | None

    @property
    def tag_list(self) -> list[str]:
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]


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

    result: JSONField[Any | None] = JSONField(
        default=None,
        null=True,
        blank=True,
    )

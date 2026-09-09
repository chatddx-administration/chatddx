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
    # Django synthesizes these alongside their ForeignKeys, but django-types
    # doesn't model that.
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

    scorer = CharField(
        max_length=255,
        blank=True,
        default="",
        help_text=(
            "Dotted import path to the function that scores this "
            "experiment's completed Runs, e.g. "
            "'chatddx.experiment.scorers.exact_match'. The worker resolves "
            "and calls it once per completed Run (see "
            "chatddx.experiment.worker.score_run); left blank, completed "
            "Runs of this experiment are never scored."
        ),
    )

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
    # Django synthesizes these alongside their ForeignKeys, but django-types
    # doesn't model that.
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
        help_text=(
            "Whatever the experiment's scorer function returned for this "
            "Run (see ExperimentModel.scorer); set once the Run reaches "
            "RunStatusChoices.SCORED."
        ),
    )

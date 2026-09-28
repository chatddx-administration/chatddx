# pyright: basic
from __future__ import annotations

from enum import IntEnum, StrEnum

from django.db.models import (
    CASCADE,
    PROTECT,
    SET_NULL,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    Model,
    OneToOneField,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    TextField,
    UUIDField,
)

from chatddx.core.models import IdentityModel
from chatddx.history.models import RunModel, TrialModel
from chatddx.repo.entities.coercion.django import CoercionBranchModel
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.instruction.django import InstructionBranchModel
from chatddx.repo.entities.output.django import OutputBranchModel
from chatddx.repo.entities.reasoning.django import ReasoningBranchModel
from chatddx.repo.entities.sampling.django import SamplingBranchModel
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.entities.toolset.django import ToolsetBranchModel

__all__ = ["ControlsModel", "JobModel", "WorkerStateModel"]


class Status(StrEnum):
    STORED = "stored"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    ERRORED = "errored"
    ABORTED = "aborted"
    STOPPED = "stopped"
    SKIPPED = "skipped"
    LOST = "lost"


UNDER_WAY = (Status.QUEUED, Status.RUNNING)

TAKEN_UP = (
    Status.COMPLETED,
    Status.ERRORED,
    Status.ABORTED,
    Status.SKIPPED,
    Status.LOST,
)

UNFINISHED = (
    Status.STORED,
    Status.ERRORED,
    Status.ABORTED,
    Status.STOPPED,
    Status.SKIPPED,
    Status.LOST,
)

STOPPED_BY = (Status.STOPPED, Status.ABORTED)
FAILED = (Status.ERRORED, Status.SKIPPED, Status.LOST)


class Stopping(IntEnum):
    NO = 0
    AFTER = 1
    NOW = 2


class JobModel(Model):
    class Meta:
        app_label = "worker"
        db_table = "worker_job"
        ordering = ("pk",)

    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
        related_name="+",
    )
    owner_id: int
    batch = UUIDField(db_index=True)

    trial = ForeignKey(
        TrialModel,
        on_delete=PROTECT,
        related_name="jobs",
    )
    trial_id: int
    configuration_branch = ForeignKey(
        ConfigurationBranchModel,
        on_delete=PROTECT,
        related_name="+",
    )
    configuration_branch_id: int
    stack_branch = ForeignKey(
        StackBranchModel,
        on_delete=PROTECT,
        related_name="+",
    )
    stack_branch_id: int
    instruction_branch = ForeignKey(
        InstructionBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="+",
    )
    instruction_branch_id: int | None
    output_branch = ForeignKey(
        OutputBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="+",
    )
    output_branch_id: int | None
    coercion_branch = ForeignKey(
        CoercionBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="+",
    )
    coercion_branch_id: int | None
    reasoning_branch = ForeignKey(
        ReasoningBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="+",
    )
    reasoning_branch_id: int | None
    sampling_branch = ForeignKey(
        SamplingBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="+",
    )
    sampling_branch_id: int | None
    toolset_branch = ForeignKey(
        ToolsetBranchModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="+",
    )
    toolset_branch_id: int | None

    status = CharField(max_length=16, default=Status.QUEUED.value, db_index=True)
    reason = TextField(
        default=None,
        null=True,
        blank=True,
    )
    queued = DateTimeField(
        default=None,
        null=True,
        blank=True,
    )
    tokens = PositiveIntegerField(default=0)
    counted = BooleanField(default=False)
    started = DateTimeField(
        default=None,
        null=True,
        blank=True,
    )
    beat = DateTimeField(
        default=None,
        null=True,
        blank=True,
    )
    finished = DateTimeField(
        default=None,
        null=True,
        blank=True,
    )
    run = ForeignKey(
        RunModel,
        default=None,
        null=True,
        blank=True,
        on_delete=SET_NULL,
        related_name="+",
    )
    run_id: int | None

    @property
    def tallied(self) -> str:
        return (
            str(self.tokens) if self.counted or not self.tokens else f"~{self.tokens}"
        )


class ControlsModel(Model):
    class Meta:
        app_label = "worker"
        db_table = "worker_controls"

    owner = OneToOneField(
        IdentityModel,
        on_delete=CASCADE,
        related_name="+",
    )
    owner_id: int
    paused = BooleanField(default=False)
    stopping = PositiveSmallIntegerField(default=Stopping.NO.value)

    @classmethod
    def of(cls, owner: IdentityModel, lock: bool = False) -> ControlsModel:
        qs = cls.objects.select_for_update() if lock else cls.objects.all()
        controls, _ = qs.get_or_create(owner=owner)

        return controls

    @classmethod
    def holding(cls) -> list[int]:
        return list(
            cls.objects.exclude(paused=False, stopping=Stopping.NO).values_list(
                "owner_id", flat=True
            )
        )


class WorkerStateModel(Model):
    class Meta:
        app_label = "worker"
        db_table = "worker_state"

    seen = DateTimeField(
        default=None,
        null=True,
        blank=True,
    )

    @classmethod
    def row(cls, lock: bool = False) -> WorkerStateModel:
        qs = cls.objects.select_for_update() if lock else cls.objects.all()
        state, _ = qs.get_or_create(pk=1)

        return state

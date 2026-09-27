from __future__ import annotations

from enum import IntEnum, StrEnum

from django.db.models import (
    CASCADE,
    PROTECT,
    SET_NULL,
    BigIntegerField,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    JSONField,
    Model,
    OneToOneField,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    TextField,
    UUIDField,
)

from chatddx.bench.cell import Kept
from chatddx.core.models import IdentityModel
from chatddx.history.models import RunModel
from chatddx.repo.entities.case.django import CaseTrailModel

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

    configuration = CharField(max_length=255)
    stack = CharField(max_length=255, db_index=True)
    set: JSONField[dict[str, str]] = JSONField(default=dict, blank=True)
    label = CharField(max_length=255)
    fingerprint = CharField(max_length=128)
    case = CharField(max_length=255)
    case_trail = ForeignKey(
        CaseTrailModel,
        on_delete=PROTECT,
        related_name="+",
    )
    case_trail_id: int
    seed = BigIntegerField(
        default=None,
        null=True,
        blank=True,
    )

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
    def kept(self) -> Kept:
        return Kept(
            self.configuration,
            self.stack,
            self.set,
            self.label,
            self.fingerprint,
            self.seed,
        )

    @property
    def cell(self) -> str:
        return f"{self.label} × {self.stack}"

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

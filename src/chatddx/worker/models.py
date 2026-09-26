# pyright: basic
"""
The worker's queue: each job a trial of a batch's, kept for later or put in
the queue, run once a slot of its stack's comes free, and how it went; what
each owner asked of the worker, to pause their jobs or stop them; and when
the worker was last at the queue.
"""

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
    # kept for later: in the queue once its batch is run
    STORED = "stored"
    # in the queue, till a slot of its stack's comes free
    QUEUED = "queued"
    RUNNING = "running"
    # the LLM answered, however well, and the run is written down
    COMPLETED = "completed"
    # the LLM or the server failed, or the run couldn't be written down
    ERRORED = "errored"
    # stopped as it ran, written down as stopped
    ABORTED = "aborted"
    # taken out of the queue by a stop before its turn
    STOPPED = "stopped"
    # not sent: what stood in its way when its turn came is its reason
    SKIPPED = "skipped"
    # its worker went away while it ran
    LOST = "lost"


# what is on its way: in the queue, or running
UNDER_WAY = (Status.QUEUED, Status.RUNNING)

# what the worker took up and is done with, one way or another
TAKEN_UP = (
    Status.COMPLETED,
    Status.ERRORED,
    Status.ABORTED,
    Status.SKIPPED,
    Status.LOST,
)

# what a batch resumed runs: all but what completed, and what is on its way
UNFINISHED = (
    Status.STORED,
    Status.ERRORED,
    Status.ABORTED,
    Status.STOPPED,
    Status.SKIPPED,
    Status.LOST,
)

# what a stop took out, and what went wrong otherwise
STOPPED_BY = (Status.STOPPED, Status.ABORTED)
FAILED = (Status.ERRORED, Status.SKIPPED, Status.LOST)


class Stopping(IntEnum):
    NO = 0
    # once the jobs running are done
    AFTER = 1
    # the jobs running too, written down as stopped
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
    # what put it in, as it names itself: the portal's batch
    batch = UUIDField(db_index=True)

    # the trial: the cell as its batch keeps it (Kept), the case, the seed
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
    # when it was put in the queue last: its place in it
    queued = DateTimeField(
        default=None,
        null=True,
        blank=True,
    )
    # what the LLM has written so far, and whether the server counted it
    tokens = PositiveIntegerField(default=0)
    counted = BooleanField(default=False)
    started = DateTimeField(
        default=None,
        null=True,
        blank=True,
    )
    # when the worker last said it was still at it
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
        """Its tokens, as the repl's batch tallies them."""
        return (
            str(self.tokens) if self.counted or not self.tokens else f"~{self.tokens}"
        )


class ControlsModel(Model):
    """What an owner asked of the worker: to pause their jobs, or to stop them."""

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
        """The owner's, held till the transaction under way ends where `lock`."""
        qs = cls.objects.select_for_update() if lock else cls.objects.all()
        controls, _ = qs.get_or_create(owner=owner)

        return controls

    @classmethod
    def holding(cls) -> list[int]:
        """The owners whose jobs wait in the queue: paused, or stopping."""
        return list(
            cls.objects.exclude(paused=False, stopping=Stopping.NO).values_list(
                "owner_id", flat=True
            )
        )


class WorkerStateModel(Model):
    """When the worker was last at the queue: one row."""

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
        """The one row, held till the transaction under way ends where `lock`."""
        qs = cls.objects.select_for_update() if lock else cls.objects.all()
        state, _ = qs.get_or_create(pk=1)

        return state

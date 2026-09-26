# pyright: basic
"""
The worker's queue: the trials put in it, run one after another, and how
each went; and the controls it heeds, between cases and during one.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

from django.db.models import (
    PROTECT,
    SET_NULL,
    BigIntegerField,
    BooleanField,
    CharField,
    DateTimeField,
    ForeignKey,
    JSONField,
    Model,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    TextField,
    UUIDField,
)

from chatddx.core.models import IdentityModel
from chatddx.history.models import RunModel
from chatddx.repo.entities.case.django import CaseTrailModel

__all__ = ["QueuedModel", "WorkerStateModel"]


class Status(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    # written down, as completed, errored or stopped as the run's record says
    DONE = "done"
    # not sent: what stood in its way when its turn came is its reason
    SKIPPED = "skipped"
    # taken out of the queue before its turn by a stop
    CANCELLED = "cancelled"
    # sent, and not written down, its reason why
    FAILED = "failed"
    # its worker went away while it ran
    LOST = "lost"


# what has been taken off the queue for good
FINISHED = (Status.DONE, Status.SKIPPED, Status.FAILED, Status.LOST)


class Stopping(IntEnum):
    NO = 0
    # when the case under way is done
    AFTER = 1
    # the case under way too, written down as stopped
    NOW = 2


class QueuedModel(Model):
    class Meta:
        app_label = "worker"
        db_table = "worker_queued"
        ordering = ("pk",)

    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
        related_name="+",
    )
    owner_id: int
    # what put it in the queue, as it names itself: the portal's batch
    batch = UUIDField(
        default=None,
        null=True,
        blank=True,
        db_index=True,
    )
    # the stretch of the queue it came in on: from empty to empty again
    drain = PositiveIntegerField(db_index=True)
    queued = DateTimeField(auto_now_add=True)

    # the trial: the cell by what its owner calls its configuration and
    # stack, what is set in it by name, and the fingerprint of the
    # configuration it came to when it was planned; the case; the seed
    configuration = CharField(max_length=255)
    stack = CharField(max_length=255)
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
    def cell(self) -> str:
        return f"{self.label} × {self.stack}"

    @property
    def tallied(self) -> str:
        """Its tokens, as the repl's batch tallies them."""
        return (
            str(self.tokens) if self.counted or not self.tokens else f"~{self.tokens}"
        )


class WorkerStateModel(Model):
    """The worker's controls, and when it was last seen: one row."""

    class Meta:
        app_label = "worker"
        db_table = "worker_state"

    paused = BooleanField(default=False)
    stopping = PositiveSmallIntegerField(default=Stopping.NO.value)
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

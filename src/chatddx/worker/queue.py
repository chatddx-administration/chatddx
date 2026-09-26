# pyright: basic
"""
The worker's queue, for the worker and for whoever watches it: a batch's
jobs put in, stored for later or queued, and queued again; how a batch's
jobs stand, and an owner's; what runs on a stack, and how many jobs are
ahead of an owner's there; an owner's job up next, and the jobs they had
the worker take up last. The queue is first come, first served, on each
stack's slots: its max_jobs.
"""

from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol
from uuid import UUID

from django.db.models import Count, Min, Q, QuerySet
from django.utils import timezone

from chatddx.bench.cell import Kept
from chatddx.core.models import IdentityModel
from chatddx.worker.models import (
    FAILED,
    STOPPED_BY,
    TAKEN_UP,
    UNDER_WAY,
    UNFINISHED,
    ControlsModel,
    JobModel,
    Status,
)

# seconds without a beat after which a job running is lost
LOST = 30


class Case(Protocol):
    """A case as a job holds it: by its name, and its trail. A branch is one."""

    # a str, and a branch's CharField
    @property
    def name(self) -> Any: ...

    @property
    def trail_id(self) -> int: ...


def put(
    owner: str,
    batch: UUID,
    cells: Sequence[Kept],
    cases: Sequence[Case],
    run: bool = True,
) -> int:
    """The cells' trials on the cases, cell by cell and case by case: queued, or stored."""
    identity = IdentityModel.objects.get(name=owner)
    queued = timezone.now() if run else None
    jobs = [
        JobModel(
            owner=identity,
            batch=batch,
            configuration=kept.configuration,
            stack=kept.stack,
            set=dict(kept.set),
            label=kept.label,
            fingerprint=kept.fingerprint,
            case=case.name,
            case_trail_id=case.trail_id,
            seed=kept.seed,
            status=Status.QUEUED if run else Status.STORED,
            queued=queued,
        )
        for kept in cells
        for case in cases
    ]

    return len(JobModel.objects.bulk_create(jobs))


def resume(owner: str, batch: UUID) -> int:
    """What of the batch hasn't completed, and isn't on its way, queued again."""
    return _queued(
        JobModel.objects.filter(owner__name=owner, batch=batch, status__in=UNFINISHED)
    )


def rerun(owner: str, batch: UUID) -> int:
    """The batch queued again, all of it that isn't on its way."""
    return _queued(
        JobModel.objects.filter(owner__name=owner, batch=batch).exclude(
            status__in=UNDER_WAY
        )
    )


def _queued(jobs: QuerySet[JobModel]) -> int:
    # in the queue behind what is there, in the order the batch put them in
    return jobs.update(
        status=Status.QUEUED,
        reason=None,
        queued=timezone.now(),
        tokens=0,
        counted=False,
        started=None,
        beat=None,
        finished=None,
        run=None,
    )


def stop(owner: str, reason: str) -> int:
    """What of the owner's is queued, taken out of the queue before its turn."""
    return JobModel.objects.filter(owner__name=owner, status=Status.QUEUED).update(
        status=Status.STOPPED, reason=reason, finished=timezone.now()
    )


def lose(sparing: Collection[int] = ()) -> int:
    """
    What ran without a beat for long enough, lost with its worker: all but
    `sparing`, what the worker asking runs itself.
    """
    now = timezone.now()

    return (
        JobModel.objects.filter(
            status=Status.RUNNING, beat__lt=now - timedelta(seconds=LOST)
        )
        .exclude(pk__in=sparing)
        .update(
            status=Status.LOST,
            reason="the worker went away while it ran",
            finished=now,
        )
    )


@dataclass(frozen=True)
class Counts:
    """How jobs stand: in all, and by where each is at."""

    total: int = 0
    stored: int = 0
    queued: int = 0
    running: int = 0
    completed: int = 0
    # taken out, or stopped as they ran
    stopped: int = 0
    # errored, skipped or lost
    failed: int = 0

    def share(self, count: int) -> float:
        """A count, as a share of all, in percent."""
        return 100 * count / self.total if self.total else 0.0

    @property
    def under_way(self) -> int:
        return self.queued + self.running


COUNTED: dict[str, Any] = {
    "total": Count("pk"),
    "stored": Count("pk", filter=Q(status=Status.STORED)),
    "queued": Count("pk", filter=Q(status=Status.QUEUED)),
    "running": Count("pk", filter=Q(status=Status.RUNNING)),
    "completed": Count("pk", filter=Q(status=Status.COMPLETED)),
    "stopped": Count("pk", filter=Q(status__in=STOPPED_BY)),
    "failed": Count("pk", filter=Q(status__in=FAILED)),
}


def counts(batches: Iterable[UUID]) -> Counts:
    """How the jobs of `batches` stand, together."""
    return Counts(
        **JobModel.objects.filter(batch__in=list(batches)).aggregate(**COUNTED)
    )


def under_way(owner: str) -> list[UUID]:
    """The owner's batches with jobs on their way, the one queued earliest first."""
    return [
        row["batch"]
        for row in JobModel.objects.filter(owner__name=owner, status__in=UNDER_WAY)
        .values("batch")
        .annotate(first=Min("queued"))
        .order_by("first")
    ]


def last(owner: str) -> UUID | None:
    """The batch of the owner's job that went its way last."""
    return (
        JobModel.objects.filter(owner__name=owner, finished__isnull=False)
        .order_by("-finished", "-pk")
        .values_list("batch", flat=True)
        .first()
    )


def running(owner: str | None = None, stack: str | None = None) -> list[JobModel]:
    """The jobs running, their beat fresh: the owner's, on the stack, where given."""
    jobs = JobModel.objects.filter(
        status=Status.RUNNING,
        beat__gte=timezone.now() - timedelta(seconds=LOST),
    )

    if owner is not None:
        jobs = jobs.filter(owner__name=owner)

    if stack is not None:
        jobs = jobs.filter(stack=stack)

    return list(jobs.select_related("owner").order_by("started", "pk"))


def in_turn(jobs: QuerySet[JobModel]) -> QuerySet[JobModel]:
    """The jobs queued of `jobs`, first come first: the queue's order."""
    return jobs.filter(status=Status.QUEUED).order_by("queued", "pk")


def up_next(owner: str, stack: str | None = None) -> JobModel | None:
    """The owner's job queued first: on the stack, where one is given."""
    jobs = JobModel.objects.filter(owner__name=owner)

    return in_turn(jobs if stack is None else jobs.filter(stack=stack)).first()


def outstanding(owner: str) -> int:
    """How many of the owner's jobs are queued."""
    return JobModel.objects.filter(owner__name=owner, status=Status.QUEUED).count()


@dataclass(frozen=True)
class Waiting:
    """
    An owner's jobs on a stack, waiting for their turn: others' run in its
    slots, or are queued ahead of theirs.
    """

    stack: str
    max_jobs: int
    # others' jobs running on the stack, and queued ahead of the owner's first
    running: int
    queued: int

    @property
    def ahead(self) -> int:
        return self.running + self.queued


def waiting(owner: str, max_jobs: Callable[[str], int]) -> list[Waiting]:
    """
    Each stack the owner's jobs wait on for their turn: none of theirs runs
    on it, and its slots are taken, or others' jobs come before theirs. The
    jobs of an owner who paused or stopped come before no one's.
    """
    holding = ControlsModel.holding()
    found: list[Waiting] = []
    mine = JobModel.objects.filter(owner__name=owner)
    others = JobModel.objects.exclude(owner__name=owner).exclude(owner_id__in=holding)
    stacks = in_turn(mine).order_by().values_list("stack", flat=True).distinct()

    for stack in sorted(stacks):
        if running(owner, stack):
            continue

        first = in_turn(mine.filter(stack=stack)).first()
        assert first is not None and first.queued is not None
        ahead = in_turn(others.filter(stack=stack)).filter(
            Q(queued__lt=first.queued) | Q(queued=first.queued, pk__lt=first.pk)
        )
        waits = Waiting(
            stack,
            max_jobs(stack),
            running=len(running(stack=stack)),
            queued=ahead.count(),
        )

        if waits.queued or waits.running >= waits.max_jobs:
            found.append(waits)

    return found


def latest(owner: str, count: int = 10) -> list[JobModel]:
    """The owner's jobs the worker took up last, the latest first, with their scores."""
    return list(
        JobModel.objects.filter(owner__name=owner, status__in=TAKEN_UP)
        .select_related("owner", "run")
        .prefetch_related("run__scores")
        .order_by("-finished", "-pk")[:count]
    )

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from django.db.models import Count, Min, Q, QuerySet
from django.utils import timezone

from chatddx.bench.bench import Trial
from chatddx.core.models import IdentityModel
from chatddx.history.record import trial_of
from chatddx.repo.entities.configuration.django import ConfigurationTrailModel
from chatddx.repo.entities.configuration.pydantic import SLICES
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.entities.stack.pydantic import StackDetails
from chatddx.repo.store.trail import dump_trail
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

LOST = 30

type Slot = tuple[int, str]

SLOT = ("stack_branch__owner_id", "stack_branch__name")

READ = (
    "owner",
    "trial__case",
    "trial__configuration",
    "configuration_branch__owner",
    "configuration_branch__trail",
    "stack_branch__owner",
    *(f"{entity}_branch" for entity in SLICES),
)


def with_read(jobs: QuerySet[JobModel]) -> QuerySet[JobModel]:
    return jobs.select_related(*READ)


def slot_of(stack: StackBranchModel) -> Slot:
    return (stack.owner_id, stack.name)


def on(jobs: QuerySet[JobModel], slot: Slot) -> QuerySet[JobModel]:
    owner_id, name = slot
    return jobs.filter(stack_branch__owner_id=owner_id, stack_branch__name=name)


def slots(slot: Slot) -> int:
    owner_id, name = slot
    details = (
        StackBranchModel.objects.filter(owner_id=owner_id, name=name)
        .order_by("-timestamp", "-id")
        .values_list("details", flat=True)
        .first()
    )

    return 1 if details is None else StackDetails.model_validate(details).max_jobs


def put(owner: str, batch: UUID, trials: Iterable[Trial], run: bool = True) -> int:
    identity = IdentityModel.objects.get(name=owner)
    queued = timezone.now() if run else None
    configurations: dict[str, ConfigurationTrailModel] = {}
    jobs: list[JobModel] = []

    for trial in trials:
        cell = trial.ready.cell
        assert cell.configuration and cell.stack
        made = cell.trail

        if made.fingerprint not in configurations:
            configurations[made.fingerprint] = dump_trail(ConfigurationTrailModel, made)

        jobs.append(
            JobModel(
                owner=identity,
                batch=batch,
                trial=trial.planned
                or trial_of(
                    configurations[made.fingerprint],
                    cell.stack.trail.id,
                    trial.case,
                    trial.seed,
                ),
                configuration_branch_id=cell.configuration.id,
                stack_branch_id=cell.stack.id,
                **{f"{entity}_branch_id": pk for entity, pk in cell.set_ids.items()},
                status=Status.QUEUED if run else Status.STORED,
                queued=queued,
            )
        )

    return len(JobModel.objects.bulk_create(jobs))


def resume(owner: str, batch: UUID) -> int:
    return _queued(
        JobModel.objects.filter(owner__name=owner, batch=batch, status__in=UNFINISHED)
    )


def rerun(owner: str, batch: UUID) -> int:
    return _queued(
        JobModel.objects.filter(owner__name=owner, batch=batch).exclude(
            status__in=UNDER_WAY
        )
    )


def _queued(jobs: QuerySet[JobModel]) -> int:
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
    return JobModel.objects.filter(owner__name=owner, status=Status.QUEUED).update(
        status=Status.STOPPED, reason=reason, finished=timezone.now()
    )


def lose(sparing: Collection[int] = ()) -> int:
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
    total: int = 0
    stored: int = 0
    queued: int = 0
    running: int = 0
    completed: int = 0
    stopped: int = 0
    failed: int = 0

    def share(self, count: int) -> float:
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
    return Counts(
        **JobModel.objects.filter(batch__in=list(batches)).aggregate(**COUNTED)
    )


def under_way(owner: str) -> list[UUID]:
    return [
        row["batch"]
        for row in JobModel.objects.filter(owner__name=owner, status__in=UNDER_WAY)
        .values("batch")
        .annotate(first=Min("queued"))
        .order_by("first")
    ]


def last(owner: str) -> UUID | None:
    return (
        JobModel.objects.filter(owner__name=owner, finished__isnull=False)
        .order_by("-finished", "-pk")
        .values_list("batch", flat=True)
        .first()
    )


def running(owner: str | None = None, slot: Slot | None = None) -> list[JobModel]:
    jobs = JobModel.objects.filter(
        status=Status.RUNNING,
        beat__gte=timezone.now() - timedelta(seconds=LOST),
    )

    if owner is not None:
        jobs = jobs.filter(owner__name=owner)

    if slot is not None:
        jobs = on(jobs, slot)

    return list(with_read(jobs).order_by("started", "pk"))


def in_turn(jobs: QuerySet[JobModel]) -> QuerySet[JobModel]:
    return jobs.filter(status=Status.QUEUED).order_by("queued", "pk")


def up_next(owner: str, slot: Slot | None = None) -> JobModel | None:
    jobs = JobModel.objects.filter(owner__name=owner)

    return with_read(in_turn(jobs if slot is None else on(jobs, slot))).first()


def outstanding(owner: str) -> int:
    return JobModel.objects.filter(owner__name=owner, status=Status.QUEUED).count()


@dataclass(frozen=True)
class Waiting:
    slot: Slot
    stack: str
    max_jobs: int
    running: int
    queued: int

    @property
    def ahead(self) -> int:
        return self.running + self.queued


def waiting(owner: str) -> list[Waiting]:
    holding = ControlsModel.holding()
    found: list[Waiting] = []
    mine = JobModel.objects.filter(owner__name=owner)
    others = JobModel.objects.exclude(owner__name=owner).exclude(owner_id__in=holding)
    queued_on: list[Slot] = sorted(
        set(in_turn(mine).order_by().values_list(*SLOT)),
        key=lambda slot: (slot[1], slot[0]),
    )

    for slot in queued_on:
        if running(owner, slot):
            continue

        first = in_turn(on(mine, slot)).first()
        assert first is not None and first.queued is not None
        ahead = in_turn(on(others, slot)).filter(
            Q(queued__lt=first.queued) | Q(queued=first.queued, pk__lt=first.pk)
        )
        waits = Waiting(
            slot,
            slot[1],
            slots(slot),
            running=len(running(slot=slot)),
            queued=ahead.count(),
        )

        if waits.queued or waits.running >= waits.max_jobs:
            found.append(waits)

    return found


def latest(owner: str, count: int = 10) -> list[JobModel]:
    return list(
        with_read(JobModel.objects.filter(owner__name=owner, status__in=TAKEN_UP))
        .select_related("run")
        .prefetch_related("run__scores")
        .order_by("-finished", "-pk")[:count]
    )

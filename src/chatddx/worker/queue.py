# pyright: basic
"""
The worker's queue: a plan's trials put in, and how it stands, for the
worker and for whoever watches it: the drain under way (from an empty queue
to an empty queue again), the case running, and the cases taken up last.
"""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from chatddx.bench.plan import Plan
from chatddx.core.models import IdentityModel
from chatddx.worker.models import FINISHED, QueuedModel, Status

# seconds without a beat after which a case running is lost
LOST = 30


def put(owner: str, plan: Plan, batch: UUID | None = None) -> int:
    """
    The plan's trials in the queue, cell by cell and case by case: in the
    drain under way, or in a new one where the queue stood empty.
    """
    identity = IdentityModel.objects.get(name=owner)
    rows: list[QueuedModel] = []

    with transaction.atomic():
        latest = QueuedModel.objects.aggregate(drain=Max("drain"))["drain"] or 0
        pending = QueuedModel.objects.filter(
            status__in=(Status.QUEUED, Status.RUNNING)
        ).exists()
        drain = latest if pending else latest + 1

        for ready in plan.ready:
            cell = ready.cell
            assert cell.stack
            fingerprint = cell.fingerprint
            seed = plan.seed_of(ready)

            for case in plan.cases:
                rows.append(
                    QueuedModel(
                        owner=identity,
                        batch=batch,
                        drain=drain,
                        configuration=cell.name,
                        stack=cell.stack.name,
                        set=cell.set_names,
                        label=cell.label,
                        fingerprint=fingerprint,
                        case=case.name,
                        case_trail_id=case.trail_id,
                        seed=seed,
                    )
                )

        _ = QueuedModel.objects.bulk_create(rows)

    return len(rows)


def cancel(reason: str) -> int:
    """What is queued, taken out of the queue before its turn."""
    return QueuedModel.objects.filter(status=Status.QUEUED).update(
        status=Status.CANCELLED, reason=reason, finished=timezone.now()
    )


def lose() -> int:
    """What ran without a beat for long enough, lost with its worker."""
    now = timezone.now()

    return QueuedModel.objects.filter(
        status=Status.RUNNING, beat__lt=now - timedelta(seconds=LOST)
    ).update(
        status=Status.LOST,
        reason="the worker went away while it ran",
        finished=now,
    )


@dataclass(frozen=True)
class Drain:
    """How far the drain under way, or the last, has come."""

    total: int
    queued: int
    running: int
    finished: int
    cancelled: int

    def share(self, count: int) -> float:
        """A count, as a share of the drain in percent."""
        return 100 * count / self.total if self.total else 0.0


def drain() -> Drain | None:
    latest = QueuedModel.objects.aggregate(drain=Max("drain"))["drain"]

    if latest is None:
        return None

    return Drain(
        **QueuedModel.objects.filter(drain=latest).aggregate(
            total=Count("pk"),
            queued=Count("pk", filter=Q(status=Status.QUEUED)),
            running=Count("pk", filter=Q(status=Status.RUNNING)),
            finished=Count("pk", filter=Q(status__in=FINISHED)),
            cancelled=Count("pk", filter=Q(status=Status.CANCELLED)),
        )
    )


def running() -> QueuedModel | None:
    """The case the worker is at, if it is at one."""
    return (
        QueuedModel.objects.filter(
            status=Status.RUNNING,
            beat__gte=timezone.now() - timedelta(seconds=LOST),
        )
        .select_related("owner")
        .first()
    )


def latest(count: int = 10) -> list[QueuedModel]:
    """The cases the worker took up last, the latest first, with their scores."""
    return list(
        QueuedModel.objects.filter(status__in=FINISHED)
        .select_related("owner", "run")
        .prefetch_related("run__scores")
        .order_by("-finished", "-pk")[:count]
    )

# pyright: basic
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy, ngettext

from chatddx.bench.bench import Bench
from chatddx.django.portal.configurations import (
    page_named as configuration_page_named,
    page_of_run as configuration_page_of,
)
from chatddx.django.portal.models import BatchModel
from chatddx.django.portal.stacks import page_named, page_of_run
from chatddx.history.models import RunModel, RunStatus
from chatddx.repo.store.branch import AmbiguousBranchError, BranchNotFoundError
from chatddx.worker import control, queue
from chatddx.worker.models import JobModel, Status, Stopping

LATEST = 10


@dataclass(frozen=True)
class Progress:
    counts: queue.Counts

    @property
    def counted(self) -> str:
        counts = self.counts

        if not counts.total:
            return _("Nothing has been queued yet.")

        said = _("%(running)d running · %(completed)d completed · %(total)d total") % {
            "running": counts.running,
            "completed": counts.completed,
            "total": counts.total,
        }

        if counts.failed:
            said += " · " + ngettext(
                "%(failed)d failed", "%(failed)d failed", counts.failed
            ) % {"failed": counts.failed}

        if counts.stopped:
            said += " · " + ngettext(
                "%(stopped)d stopped", "%(stopped)d stopped", counts.stopped
            ) % {"stopped": counts.stopped}

        return said

    def _share(self, count: int) -> str:
        return f"{self.counts.share(count):.2f}"

    @property
    def completed_share(self) -> str:
        return self._share(self.counts.completed)

    @property
    def failed_share(self) -> str:
        return self._share(self.counts.failed)

    @property
    def running_share(self) -> str:
        return self._share(self.counts.running)

    @property
    def stopped_share(self) -> str:
        return self._share(self.counts.stopped)


@dataclass(frozen=True)
class Link:
    name: str
    pk: int | None


@dataclass(frozen=True)
class Now:
    job: JobModel
    running_for: str
    configuration_page: str | None = None
    stack_page: str | None = None


@dataclass(frozen=True)
class Ran:
    when: datetime | None
    case: str
    configuration: str
    stack: str
    batch: Link
    outcome: str
    trouble: bool
    reason: str | None
    tokens: str
    scores: list[tuple[str, str]]
    run: Any = None
    configuration_page: str | None = None
    stack_page: str | None = None

    @property
    def cell(self) -> str:
        return f"{self.configuration} × {self.stack}"


@dataclass(frozen=True)
class Shown:
    state: control.State
    running: list[Now]
    up_next: JobModel | None
    up_next_configuration: str | None
    up_next_stack: str | None
    outstanding: int
    waiting: list[queue.Waiting]
    batches: list[Link]
    progress: Progress
    latest: list[Ran]

    @property
    def said(self) -> str:
        state, running = self.state, len(self.running)

        if not state.alive:
            return _("The worker isn't running: chatddx worker serve starts it.")

        if state.stopping == Stopping.NOW:
            return _("Stopping now.")

        if state.stopping == Stopping.AFTER:
            return ngettext(
                "Stopping after the case running: stop again to stop it now.",
                "Stopping after the cases running: stop again to stop them now.",
                running,
            )

        if state.paused:
            return (
                ngettext(
                    "Pausing after the case running.",
                    "Pausing after the cases running.",
                    running,
                )
                if running
                else _("Paused.")
            )

        if running:
            return _("Running.")

        if self.waiting:
            return _("Waiting for our turn.")

        if self.outstanding:
            return _("Queued: up next.")

        return _("Idle: nothing of yours is queued.")

    @property
    def stoppable(self) -> bool:
        return bool(self.running) or bool(self.outstanding)

    @property
    def stop_attrs(self) -> dict[str, str]:
        if not self.stoppable or self.state.stopping == Stopping.NOW:
            return {"disabled": "disabled"}

        return {}


def shown(owner: str) -> Shown:
    batches = queue.under_way(owner)

    if not batches:
        last = queue.last(owner)
        batches = [] if last is None else [last]

    latest = queue.latest(owner, LATEST)
    links = links_of(owner, [*batches, *(job.batch for job in latest)])
    pages = Pages(owner)
    up_next = queue.up_next(owner)

    return Shown(
        state=control.state(owner),
        running=[
            Now(job, running_for(job), pages.configuration(job), pages.stack(job.stack))
            for job in queue.running(owner)
        ],
        up_next=up_next,
        up_next_configuration=pages.configuration(up_next) if up_next else None,
        up_next_stack=pages.stack(up_next.stack) if up_next else None,
        outstanding=queue.outstanding(owner),
        waiting=queue.waiting(owner, max_jobs_of(owner)),
        batches=[links[batch] for batch in batches],
        progress=Progress(queue.counts(batches)),
        latest=[ran(job, links[job.batch], pages) for job in latest],
    )


class Pages:
    def __init__(self, owner: str):
        self.owner: str = owner
        self._found: dict[Any, str | None] = {}

    def stack(self, name: str) -> str | None:
        return self._once(("stack", name), lambda: page_named(self.owner, name))

    def configuration(self, job: JobModel) -> str | None:
        return self._once(
            ("configuration", job.configuration, tuple(sorted(job.set.items()))),
            lambda: configuration_page_named(self.owner, job.configuration, job.set),
        )

    def _once(self, key: Any, found: Callable[[], str | None]) -> str | None:
        if key not in self._found:
            self._found[key] = found()

        return self._found[key]


def links_of(owner: str, batches: list[UUID]) -> dict[UUID, Link]:
    pks = dict(
        BatchModel.objects.filter(owner__name=owner, uuid__in=batches).values_list(
            "uuid", "pk"
        )
    )

    return {batch: Link(str(batch)[:8], pks.get(batch)) for batch in batches}


def max_jobs_of(owner: str) -> Any:
    bench = Bench(owner)

    def max_jobs(stack: str) -> int:
        try:
            return bench.max_jobs(stack)
        except (BranchNotFoundError, AmbiguousBranchError):
            return 1

    return max_jobs


def running_for(job: JobModel) -> str:
    if job.started is None:
        return ""

    seconds = int((timezone.now() - job.started).total_seconds())
    minutes, seconds = divmod(seconds, 60)

    return f"{minutes}:{seconds:02}" if minutes else f"{seconds} s"


def ran(job: JobModel, batch: Link, pages: Pages) -> Ran:
    run = job.run
    outcome, trouble, reason = _outcome(job, run)
    latest: dict[str, str] = {}

    for score in sorted(run.scores.all(), key=lambda score: score.pk) if run else []:
        latest[score.scorer_name] = value_of(score.value)

    return Ran(
        when=job.finished,
        case=job.case,
        configuration=job.label,
        stack=job.stack,
        batch=batch,
        outcome=outcome,
        trouble=trouble,
        reason=reason,
        tokens=job.tallied,
        scores=sorted(latest.items()),
        run=run.uuid if run else None,
        configuration_page=(configuration_page_of(run, job) if run else None)
        or pages.configuration(job),
        stack_page=(page_of_run(run) if run else None) or pages.stack(job.stack),
    )


def value_of(value: float | None) -> str:
    if value is None:
        return "—"

    return str(int(value)) if value.is_integer() else f"{value:.3g}"


def _outcome(job: JobModel, run: RunModel | None) -> tuple[str, bool, str | None]:
    if run is None or job.status == Status.SKIPPED:
        return job.status, True, job.reason

    if job.status == Status.ABORTED:
        return "stopped", True, job.reason

    if run.status == RunStatus.ERRORED:
        return "errored", True, job.reason or run.error

    match run.valid:
        case True:
            return "valid", False, job.reason
        case False:
            return "invalid", True, job.reason or run.error
        case None:
            return "completed", False, job.reason


class BatchState(StrEnum):
    STORED = "stored"
    QUEUED = "queued"
    RUNNING = "running"
    STOPPED = "stopped"
    UNFINISHED = "unfinished"
    COMPLETED = "completed"


STATES: dict[BatchState, Any] = {
    BatchState.STORED: gettext_lazy("stored"),
    BatchState.QUEUED: gettext_lazy("queued"),
    BatchState.RUNNING: gettext_lazy("running"),
    BatchState.STOPPED: gettext_lazy("stopped"),
    BatchState.UNFINISHED: gettext_lazy("unfinished"),
    BatchState.COMPLETED: gettext_lazy("completed"),
}


def state_of(counts: queue.Counts) -> BatchState:
    if counts.running:
        return BatchState.RUNNING

    if counts.queued:
        return BatchState.QUEUED

    if counts.stored == counts.total:
        return BatchState.STORED

    if counts.completed == counts.total:
        return BatchState.COMPLETED

    return BatchState.STOPPED if counts.stopped else BatchState.UNFINISHED


ACTIONS: dict[BatchState, tuple[str, Any]] = {
    BatchState.STORED: ("resume", gettext_lazy("Run the batch")),
    BatchState.STOPPED: ("resume", gettext_lazy("Resume the batch")),
    BatchState.UNFINISHED: ("resume", gettext_lazy("Run what didn't complete")),
    BatchState.COMPLETED: ("rerun", gettext_lazy("Run it again")),
}


@dataclass(frozen=True)
class BatchShown:
    counts: queue.Counts
    state: BatchState
    paused: bool
    waiting: queue.Waiting | None
    behind: bool = False

    @property
    def progress(self) -> Progress:
        return Progress(self.counts)

    @property
    def action(self) -> tuple[str, Any] | None:
        return ACTIONS.get(self.state)

    @property
    def said(self) -> str:
        counts = self.counts
        done = {"completed": counts.completed, "total": counts.total}

        match self.state:
            case BatchState.STORED:
                return _("Kept for later: none of it has run.")
            case BatchState.QUEUED if self.paused:
                return _("Queued, and paused: resume it on the status page.")
            case BatchState.QUEUED if self.waiting:
                return ngettext(
                    "Waiting for our turn on %(stack)s: %(ahead)d case ahead of ours.",
                    "Waiting for our turn on %(stack)s: %(ahead)d cases ahead of ours.",
                    self.waiting.ahead,
                ) % {"stack": self.waiting.stack, "ahead": self.waiting.ahead}
            case BatchState.QUEUED if self.behind:
                return _("Queued, behind another batch of yours.")
            case BatchState.QUEUED:
                return _("Queued: up next.")
            case BatchState.RUNNING:
                return _("Running: %(completed)d of %(total)d completed.") % done
            case BatchState.STOPPED:
                return _("Stopped: %(completed)d of %(total)d completed.") % done
            case BatchState.UNFINISHED:
                return _("Unfinished: %(completed)d of %(total)d completed.") % done
            case BatchState.COMPLETED:
                return _("Completed: all %(total)d.") % done


def batch_shown(owner: str, batch: Any) -> BatchShown:
    counts = queue.counts([batch.uuid])
    state = state_of(counts)
    waiting = None
    behind = False

    if state == BatchState.QUEUED:
        waiting = next(
            (
                waits
                for waits in queue.waiting(owner, max_jobs_of(owner))
                if waits.stack == batch.stack
            ),
            None,
        )
        up_next = queue.up_next(owner, batch.stack)
        behind = up_next is not None and up_next.batch != batch.uuid

    return BatchShown(counts, state, control.state(owner).paused, waiting, behind)

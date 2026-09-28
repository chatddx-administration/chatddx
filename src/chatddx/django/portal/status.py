# pyright: basic
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy, ngettext

from chatddx.bench.bench import Bench
from chatddx.django.portal.configurations import (
    page_of_made,
    page_of_run as configuration_page_of,
)
from chatddx.django.portal.models import BatchModel
from chatddx.django.portal.stacks import page_of as stack_page_of, page_of_run
from chatddx.history.models import RunModel, RunStatus
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
    case: str
    label: str
    stack: str
    tokens: int
    tallied: str
    running_for: str = ""
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
    up_next: Now | None
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
    bench = Bench(owner)
    batches = queue.under_way(owner)

    if not batches:
        last = queue.last(owner)
        batches = [] if last is None else [last]

    latest = queue.latest(owner, LATEST)
    links = links_of(owner, [*batches, *(job.batch for job in latest)])
    up_next = queue.up_next(owner)

    return Shown(
        state=control.state(owner),
        running=[now(bench, job) for job in queue.running(owner)],
        up_next=now(bench, up_next) if up_next is not None else None,
        outstanding=queue.outstanding(owner),
        waiting=queue.waiting(owner),
        batches=[links[batch] for batch in batches],
        progress=Progress(queue.counts(batches)),
        latest=[ran(bench, job, links[job.batch]) for job in latest],
    )


def now(bench: Bench, job: JobModel) -> Now:
    return Now(
        case=bench.name_of("case", job.trial.case),
        label=bench.label_of(job),
        stack=job.stack_branch.name,
        tokens=job.tokens,
        tallied=job.tallied,
        running_for=running_for(job),
        configuration_page=page_of_made(job),
        stack_page=stack_page_of(job.stack_branch_id),
    )


def links_of(owner: str, batches: list[UUID]) -> dict[UUID, Link]:
    pks = dict(
        BatchModel.objects.filter(owner__name=owner, uuid__in=batches).values_list(
            "uuid", "pk"
        )
    )

    return {batch: Link(str(batch)[:8], pks.get(batch)) for batch in batches}


def running_for(job: JobModel) -> str:
    if job.started is None:
        return ""

    seconds = int((timezone.now() - job.started).total_seconds())
    minutes, seconds = divmod(seconds, 60)

    return f"{minutes}:{seconds:02}" if minutes else f"{seconds} s"


def ran(bench: Bench, job: JobModel, batch: Link) -> Ran:
    run = job.run
    outcome, trouble, reason = _outcome(job, run)
    latest: dict[str, str] = {}

    for score in sorted(run.scores.all(), key=lambda score: score.pk) if run else []:
        latest[score.scorer_name] = value_of(score.value)

    return Ran(
        when=job.finished,
        case=bench.name_of("case", job.trial.case),
        configuration=bench.label_of(job),
        stack=job.stack_branch.name,
        batch=batch,
        outcome=outcome,
        trouble=trouble,
        reason=reason,
        tokens=job.tallied,
        scores=sorted(latest.items()),
        run=run.uuid if run else None,
        configuration_page=(configuration_page_of(run) if run else None)
        or page_of_made(job),
        stack_page=(page_of_run(run) if run else None)
        or stack_page_of(job.stack_branch_id),
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
        first = (
            queue.in_turn(JobModel.objects.filter(batch=batch.uuid))
            .select_related("stack_branch")
            .first()
        )

        if first is not None:
            slot = queue.slot_of(first.stack_branch)
            waiting = next(
                (waits for waits in queue.waiting(owner) if waits.slot == slot), None
            )
            up_next = queue.up_next(owner, slot)
            behind = up_next is not None and up_next.batch != batch.uuid

    return BatchShown(counts, state, control.state(owner).paused, waiting, behind)

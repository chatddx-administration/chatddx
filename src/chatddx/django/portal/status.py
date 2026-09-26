# pyright: basic
"""
The worker as an owner's pages show it: the status page, what the worker is
at with the owner's jobs, how far their batches under way have come, what
waits its turn behind others' and how many cases are ahead, their jobs
running and up next, and those taken up last; and a batch's page, how the
batch stands and what it can do next.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy, ngettext

from chatddx.bench.bench import Bench
from chatddx.django.portal.models import BatchModel
from chatddx.history.models import RunModel, RunStatus
from chatddx.repo.store.branch import AmbiguousBranchError, BranchNotFoundError
from chatddx.worker import control, queue
from chatddx.worker.models import JobModel, Status, Stopping

# how many of the jobs taken up last the status page shows
LATEST = 10


@dataclass(frozen=True)
class Progress:
    """How far jobs have come, as a bar and its label show it."""

    counts: queue.Counts

    @property
    def counted(self) -> str:
        """The counts: running, completed, in all; and failed, and stopped."""
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
        """A count's share, in percent, as CSS reads it."""
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
    """A batch, as a page links to it: by its short name, to its own page."""

    name: str
    pk: int | None


@dataclass(frozen=True)
class Now:
    """A job running: what it is, and how long it has run."""

    job: JobModel
    running_for: str


@dataclass(frozen=True)
class Ran:
    """A job the worker took up: when, what, how it went, and its scores."""

    when: datetime | None
    case: str
    cell: str
    batch: Link
    outcome: str
    # an outcome to look into: errored, stopped or not run
    trouble: bool
    reason: str | None
    tokens: str
    scores: list[tuple[str, str]]


@dataclass(frozen=True)
class Shown:
    """The status page: the worker at an owner's jobs."""

    state: control.State
    running: list[Now]
    up_next: JobModel | None
    outstanding: int
    waiting: list[queue.Waiting]
    # the batches the progress is of: those on their way, or the last
    batches: list[Link]
    progress: Progress
    latest: list[Ran]

    @property
    def said(self) -> str:
        """What the worker is at with the owner's jobs, in a few words."""
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
        """Whether there is anything a stop would stop."""
        return bool(self.running) or bool(self.outstanding)

    @property
    def stop_attrs(self) -> dict[str, str]:
        """The stop button's, off where a stop stops nothing, or nothing more."""
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

    return Shown(
        state=control.state(owner),
        running=[Now(job, running_for(job)) for job in queue.running(owner)],
        up_next=queue.up_next(owner),
        outstanding=queue.outstanding(owner),
        waiting=queue.waiting(owner, max_jobs_of(owner)),
        batches=[links[batch] for batch in batches],
        progress=Progress(queue.counts(batches)),
        latest=[ran(job, links[job.batch]) for job in latest],
    )


def links_of(owner: str, batches: list[UUID]) -> dict[UUID, Link]:
    """The owner's batches, as a page links to them."""
    pks = dict(
        BatchModel.objects.filter(owner__name=owner, uuid__in=batches).values_list(
            "uuid", "pk"
        )
    )

    return {batch: Link(str(batch)[:8], pks.get(batch)) for batch in batches}


def max_jobs_of(owner: str) -> Any:
    """How many jobs a stack takes at once, as the owner's branch of it says."""
    bench = Bench(owner)

    def max_jobs(stack: str) -> int:
        try:
            return bench.max_jobs(stack)
        except (BranchNotFoundError, AmbiguousBranchError):
            return 1

    return max_jobs


def running_for(job: JobModel) -> str:
    """How long the job has run, as a clock says it."""
    if job.started is None:
        return ""

    seconds = int((timezone.now() - job.started).total_seconds())
    minutes, seconds = divmod(seconds, 60)

    return f"{minutes}:{seconds:02}" if minutes else f"{seconds} s"


def ran(job: JobModel, batch: Link) -> Ran:
    run = job.run
    outcome, trouble, reason = _outcome(job, run)
    latest: dict[str, str] = {}

    for score in sorted(run.scores.all(), key=lambda score: score.pk) if run else []:
        latest[score.scorer_name] = value_of(score.value)

    return Ran(
        when=job.finished,
        case=job.case,
        cell=job.cell,
        batch=batch,
        outcome=outcome,
        trouble=trouble,
        reason=reason,
        tokens=job.tallied,
        scores=sorted(latest.items()),
    )


def value_of(value: float | None) -> str:
    """A score, as the repl writes it."""
    if value is None:
        return "—"

    return str(int(value)) if value.is_integer() else f"{value:.3g}"


def _outcome(job: JobModel, run: RunModel | None) -> tuple[str, bool, str | None]:
    """How a job went, whether it is one to look into, and why, where told."""
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


# what the batches' pages call each
STATES: dict[BatchState, Any] = {
    BatchState.STORED: gettext_lazy("stored"),
    BatchState.QUEUED: gettext_lazy("queued"),
    BatchState.RUNNING: gettext_lazy("running"),
    BatchState.STOPPED: gettext_lazy("stopped"),
    BatchState.UNFINISHED: gettext_lazy("unfinished"),
    BatchState.COMPLETED: gettext_lazy("completed"),
}


def state_of(counts: queue.Counts) -> BatchState:
    """Where a batch stands, by how its jobs do."""
    if counts.running:
        return BatchState.RUNNING

    if counts.queued:
        return BatchState.QUEUED

    if counts.stored == counts.total:
        return BatchState.STORED

    if counts.completed == counts.total:
        return BatchState.COMPLETED

    return BatchState.STOPPED if counts.stopped else BatchState.UNFINISHED


# what each state's button asks of the queue, and what it says
ACTIONS: dict[BatchState, tuple[str, Any]] = {
    BatchState.STORED: ("resume", gettext_lazy("Run the batch")),
    BatchState.STOPPED: ("resume", gettext_lazy("Resume the batch")),
    BatchState.UNFINISHED: ("resume", gettext_lazy("Run what didn't complete")),
    BatchState.COMPLETED: ("rerun", gettext_lazy("Run it again")),
}


@dataclass(frozen=True)
class BatchShown:
    """A batch's page: how the batch stands, and what it can do next."""

    counts: queue.Counts
    state: BatchState
    paused: bool
    waiting: queue.Waiting | None
    # queued behind another batch of the owner's
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
        # a stack's jobs go in turn, whosever they are, the owner's too
        up_next = queue.up_next(owner, batch.stack)
        behind = up_next is not None and up_next.batch != batch.uuid

    return BatchShown(counts, state, control.state(owner).paused, waiting, behind)

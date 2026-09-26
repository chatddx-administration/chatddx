# pyright: basic
"""
The worker as the status page shows it: what it is at and how far the
drain has come, the case it runs and its tally, and the cases it took up
last, whosever batch they came from.
"""

from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone
from django.utils.translation import gettext as _, ngettext

from chatddx.history.models import RunModel, RunStatus
from chatddx.worker import control, queue
from chatddx.worker.models import QueuedModel, Status, Stopping

# how many of the cases taken up last the page shows
LATEST = 10


@dataclass(frozen=True)
class Ran:
    """A case the worker took up: when, what, how it went, and its scores."""

    when: datetime | None
    case: str
    cell: str
    owner: str
    outcome: str
    # an outcome to look into: errored, stopped or not run
    trouble: bool
    reason: str | None
    tokens: str
    scores: list[tuple[str, str]]


@dataclass(frozen=True)
class Shown:
    state: control.State
    drain: queue.Drain | None
    running: QueuedModel | None
    latest: list[Ran]

    @property
    def said(self) -> str:
        """What the worker is at, in a few words."""
        state, running = self.state, self.running

        if not state.alive:
            return _("The worker isn't running: chatddx worker serve starts it.")

        if state.stopping == Stopping.NOW:
            return _("Stopping now.")

        if state.stopping == Stopping.AFTER:
            return _("Stopping after this case: stop again to stop it now.")

        if state.paused:
            return _("Pausing after this case.") if running else _("Paused.")

        if running is None and not (self.drain and self.drain.queued):
            return _("Idle: nothing is queued.")

        return _("Running.")

    @property
    def counted(self) -> str:
        """The drain's counts: cases running, completed, in all."""
        drain = self.drain

        if drain is None:
            return _("Nothing has been queued yet.")

        said = _("%(running)d running · %(finished)d completed · %(total)d total") % {
            "running": drain.running,
            "finished": drain.finished,
            "total": drain.total,
        }

        if drain.cancelled:
            said += " · " + ngettext(
                "%(cancelled)d cancelled", "%(cancelled)d cancelled", drain.cancelled
            ) % {"cancelled": drain.cancelled}

        return said

    @property
    def stoppable(self) -> bool:
        """Whether there is anything a stop would stop."""
        return self.running is not None or bool(self.drain and self.drain.queued)

    @property
    def stop_attrs(self) -> dict[str, str]:
        """The stop button's, off where a stop stops nothing, or nothing more."""
        if not self.stoppable or self.state.stopping == Stopping.NOW:
            return {"disabled": "disabled"}

        return {}

    @property
    def finished_share(self) -> str:
        """The share of the drain finished, in percent, as CSS reads it."""
        return f"{self.drain.share(self.drain.finished):.2f}" if self.drain else "0"

    @property
    def running_share(self) -> str:
        return f"{self.drain.share(self.drain.running):.2f}" if self.drain else "0"

    @property
    def cancelled_share(self) -> str:
        return f"{self.drain.share(self.drain.cancelled):.2f}" if self.drain else "0"

    @property
    def running_for(self) -> str:
        if self.running is None or self.running.started is None:
            return ""

        seconds = int((timezone.now() - self.running.started).total_seconds())
        minutes, seconds = divmod(seconds, 60)

        return f"{minutes}:{seconds:02}" if minutes else f"{seconds} s"


def shown() -> Shown:
    return Shown(
        state=control.state(),
        drain=queue.drain(),
        running=queue.running(),
        latest=[ran(item) for item in queue.latest(LATEST)],
    )


def ran(item: QueuedModel) -> Ran:
    run = item.run
    outcome, trouble, reason = _outcome(item, run)
    latest: dict[str, str] = {}

    for score in sorted(run.scores.all(), key=lambda score: score.pk) if run else []:
        latest[score.scorer_name] = value_of(score.value)

    return Ran(
        when=item.finished,
        case=item.case,
        cell=item.cell,
        owner=item.owner.name,
        outcome=outcome,
        trouble=trouble,
        reason=reason,
        tokens=item.tallied,
        scores=sorted(latest.items()),
    )


def value_of(value: float | None) -> str:
    """A score, as the repl writes it."""
    if value is None:
        return "—"

    return str(int(value)) if value.is_integer() else f"{value:.3g}"


def _outcome(item: QueuedModel, run: RunModel | None) -> tuple[str, bool, str | None]:
    """How a case went, whether it is one to look into, and why, where told."""
    if run is None or item.status != Status.DONE:
        return item.status, True, item.reason

    if run.error == "stopped":
        return "stopped", True, item.reason

    if run.status == RunStatus.ERRORED:
        return "errored", True, item.reason or run.error

    match run.valid:
        case True:
            return "valid", False, item.reason
        case False:
            return "invalid", True, item.reason or run.error
        case None:
            return "completed", False, item.reason

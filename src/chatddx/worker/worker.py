# pyright: basic
"""
The worker: it takes the queue's trials one after another, as the repl's
batch runs its cases, and writes each down as a run of its owner's, in a
conversation held by the worker. It heeds the controls between cases, and a
stop now during one. `chatddx worker serve` keeps it at the queue, as the
host's service runs it; `chatddx worker run` runs what is queued.
"""

import logging
import math
import signal
import time
from collections.abc import Iterator
from contextlib import contextmanager
from types import FrameType
from typing import Any

from django.db import connections, transaction
from django.utils import timezone

from chatddx.bench.bench import Bench, NotFound, NotReady, Trial
from chatddx.bench.plan import reasons
from chatddx.bench.sending import Handed, Sending, Written
from chatddx.history.models import ConversationContext
from chatddx.repo.store.branch import AmbiguousBranchError, BranchNotFoundError
from chatddx.runtime.resolution import CellRefused
from chatddx.scoring.score import Scoring
from chatddx.worker import queue
from chatddx.worker.control import STOPPED
from chatddx.worker.models import QueuedModel, Status, Stopping, WorkerStateModel

logger = logging.getLogger(__name__)

# seconds between looks at the queue while there is nothing to take
POLL = 1.0

# seconds between beats while a case runs: its tally written, a stop read
BEAT = 0.5

# where runs go in place of each stack's endpoint: the fake vLLM, in tests
TRANSPORT: Any = None


class Unrunnable(Exception):
    pass


# what keeps a trial from being sent when its turn comes
UNSENT = (
    Unrunnable,
    NotFound,
    NotReady,
    CellRefused,
    BranchNotFoundError,
    AmbiguousBranchError,
    ValueError,
)


class Worker:
    """A worker at the queue: a bench and a scoring for each owner, a drain long."""

    def __init__(self, transport: Any = None):
        self.transport: Any = TRANSPORT if transport is None else transport
        self._benches: dict[str, tuple[Bench, Scoring]] = {}

    def run(self) -> int:
        """What is queued, till the queue is empty, paused or stopped: how many."""
        taken = 0

        while self.turn() is not None:
            taken += 1

        return taken

    def serve(self) -> None:
        """The queue as it fills, till the worker is stopped."""
        while True:
            if self.turn() is None:
                # the next drain reads the registry afresh
                self._benches.clear()
                time.sleep(POLL)

    def turn(self) -> QueuedModel | None:
        """The controls heeded, then the next case taken and run: the case."""
        _let_go()
        queued = _take()

        if queued is not None:
            self._attempt(queued)

        return queued

    def _attempt(self, queued: QueuedModel) -> None:
        bench, scoring = self._bench(queued.owner.name)

        try:
            trial = _trial(bench, queued)
            sending = Sending(bench, trial, ConversationContext.WORKER, scoring)
        except UNSENT as e:
            _skipped(queued, e)
            return

        logger.info("%s", trial.description)

        try:
            _sent(queued, sending)
        finally:
            # stopped by a signal on its way, it is written down as stopped
            sending.stop()
            _written(queued, sending, sending.written())

    def _bench(self, owner: str) -> tuple[Bench, Scoring]:
        if owner not in self._benches:
            self._benches[owner] = (Bench(owner, self.transport), Scoring(owner))

        return self._benches[owner]


def run(transport: Any = None) -> int:
    return Worker(transport).run()


def serve(transport: Any = None) -> None:
    Worker(transport).serve()


@contextmanager
def terminated_as_interrupted() -> Iterator[None]:
    """A stop from the host's service taken as Ctrl-C: the case written down."""

    def interrupted(_signal: int, _frame: FrameType | None) -> None:
        raise KeyboardInterrupt

    held = signal.signal(signal.SIGTERM, interrupted)

    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, held)


def _take() -> QueuedModel | None:
    """
    The next case, running, where the controls let one run. A stop the
    worker heeds between cases takes what is queued out of the queue.
    """
    now = timezone.now()

    with transaction.atomic():
        state = WorkerStateModel.row(lock=True)
        state.seen = now
        lost = queue.lose()

        if lost:
            logger.warning("%d case(s) lost with the worker that ran them", lost)

        if state.stopping != Stopping.NO and queue.running() is None:
            cancelled = queue.cancel(STOPPED)
            state.stopping = Stopping.NO
            logger.info("stopped: %d case(s) taken out of the queue", cancelled)

        state.save(update_fields=["seen", "stopping"])

        if state.paused or state.stopping != Stopping.NO:
            return None

        queued = (
            QueuedModel.objects.select_for_update(skip_locked=True, of=("self",))
            .select_related("owner", "case_trail")
            .filter(status=Status.QUEUED)
            .order_by("pk")
            .first()
        )

        if queued is None:
            return None

        queued.status = Status.RUNNING
        queued.started = queued.beat = now
        queued.save(update_fields=["status", "started", "beat"])

    return queued


def _trial(bench: Bench, queued: QueuedModel) -> Trial:
    """The trial as it was planned, its case's vignette as it was then."""
    cell = bench.cell_of(queued.configuration, queued.stack, queued.set)

    if cell.fingerprint != queued.fingerprint:
        raise Unrunnable(f"{queued.label} is another configuration than was planned")

    case = queued.case_trail

    return Trial(bench.ready(cell), case.pk, queued.case, case.vignette, queued.seed)


def _sent(queued: QueuedModel, sending: Sending) -> None:
    """Sent, and beating as it streams: its tally written, a stop now heeded."""
    beaten = -math.inf

    with Handed(sending.events(), tick=BEAT) as handed:
        for _ in handed:
            now = time.monotonic()

            if now - beaten < BEAT:
                continue

            beaten = now

            if _beat(queued, sending) == Stopping.NOW:
                handed.stop()


def _beat(queued: QueuedModel, sending: Sending) -> Stopping:
    now = timezone.now()
    tokens = sending.tokens
    _ = QueuedModel.objects.filter(pk=queued.pk).update(
        tokens=tokens.count, counted=tokens.counted, beat=now
    )
    _ = WorkerStateModel.objects.filter(pk=1).update(seen=now)

    return Stopping(
        WorkerStateModel.objects.filter(pk=1).values_list("stopping", flat=True).first()
        or Stopping.NO
    )


def _skipped(queued: QueuedModel, error: Exception) -> None:
    match error:
        case NotReady() | CellRefused():
            reason = "; ".join(reasons(error))
        case _:
            reason = str(error)

    logger.info("skipped: %s × %s: %s", queued.cell, queued.case, reason)
    _finished(queued, Status.SKIPPED, reason)


def _written(queued: QueuedModel, sending: Sending, written: Written) -> None:
    tokens = sending.tokens
    queued.tokens, queued.counted = tokens.count, tokens.counted
    queued.run = written.run

    if written.run is None:
        _finished(queued, Status.FAILED, written.unrecorded or "nothing was sent")
    else:
        _finished(queued, Status.DONE, written.unscored)


def _finished(queued: QueuedModel, status: Status, reason: str | None) -> None:
    queued.status = status
    queued.reason = reason
    queued.finished = timezone.now()
    queued.save(
        update_fields=["status", "reason", "tokens", "counted", "run", "finished"]
    )


def _let_go() -> None:
    """A long-lived process's connections, let go where they went stale."""
    for connection in connections.all(initialized_only=True):
        if not connection.in_atomic_block:
            connection.close_if_unusable_or_obsolete()

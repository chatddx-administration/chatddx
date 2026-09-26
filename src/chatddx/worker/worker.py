# pyright: basic
"""
The worker: it runs the queue's jobs as their stacks take them, as many at
once on a stack as its max_jobs, first queued first, whosever they are.
Each runs as the repl's batch runs a case, and is written down as a run of
its owner's, in a conversation held by the worker. It heeds each owner's
controls: a paused owner's jobs wait, and a stop again stops those running.
`chatddx worker serve` keeps it at the queue, as the host's service runs
it; `chatddx worker run` runs what is queued.
"""

import logging
import math
import signal
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from types import FrameType
from typing import Any

from django.db import connections, transaction
from django.utils import timezone

from chatddx.bench.bench import Bench, NotFound, NotReady, Trial
from chatddx.bench.outcome import STOPPED
from chatddx.bench.plan import reasons
from chatddx.bench.sending import ENDED, Relay, Sending
from chatddx.history.models import ConversationContext, RunStatus
from chatddx.repo.store.branch import AmbiguousBranchError, BranchNotFoundError
from chatddx.runtime.resolution import CellRefused
from chatddx.scoring.score import Scoring
from chatddx.worker import queue
from chatddx.worker.models import (
    ControlsModel,
    JobModel,
    Status,
    Stopping,
    WorkerStateModel,
)

logger = logging.getLogger(__name__)

# seconds between looks at the queue for jobs to start
POLL = 1.0

# seconds between beats while jobs run: their tallies written, stops read
BEAT = 0.5

# where runs go in place of each stack's endpoint: the fake vLLM, in tests
TRANSPORT: Any = None

# what keeps a trial from being sent when its turn comes
UNSENT = (
    NotFound,
    NotReady,
    CellRefused,
    BranchNotFoundError,
    AmbiguousBranchError,
    ValueError,
)


@dataclass
class Running:
    """A job the worker runs: its trial on its way."""

    job: JobModel
    sending: Sending
    # a stop now asked of it
    stopped: bool = False


class Worker:
    """A worker at the queue: a bench and a scoring for each owner, a drain long."""

    def __init__(self, transport: Any = None):
        self.transport: Any = TRANSPORT if transport is None else transport
        self._benches: dict[str, tuple[Bench, Scoring]] = {}
        self._running: dict[int, Running] = {}

    def run(self) -> int:
        """What is queued, till nothing more can start: how many jobs it took up."""
        return self._work(forever=False)

    def serve(self) -> None:
        """The queue as it fills, till the worker is stopped."""
        _ = self._work(forever=True)

    def _work(self, forever: bool) -> int:
        taken = 0
        looked = beaten = -math.inf
        ended = False

        with Relay[int]() as relay:
            try:
                while True:
                    if ended or time.monotonic() - looked >= POLL:
                        _let_go()
                        taken += self._fill(relay)
                        looked, ended = time.monotonic(), False

                    if not self._running:
                        if not forever:
                            return taken

                        # the next drain reads the registry afresh
                        self._benches.clear()
                        time.sleep(POLL)
                        continue

                    for key, event in relay.taken(timeout=BEAT):
                        if event is ENDED:
                            self._end(self._running.pop(key))
                            ended = True

                    if time.monotonic() - beaten >= BEAT:
                        self._beat(relay)
                        beaten = time.monotonic()
            finally:
                # stopped by a signal, what runs is stopped with it, written
                # down as stopped; what is queued waits for the worker
                relay.close()

                for running in self._running.values():
                    self._end(running)

                self._running.clear()

    def _fill(self, relay: Relay[int]) -> int:
        """The controls heeded, and each stack's free slots taken, first come first."""
        _heeded(self._running)
        holding = ControlsModel.holding()
        taken = 0
        waiting = (
            queue.in_turn(JobModel.objects.exclude(owner_id__in=holding))
            .order_by()
            .values_list("stack", flat=True)
            .distinct()
        )

        for stack in sorted(waiting):
            free = self._max_jobs(stack, holding) - len(queue.running(stack=stack))

            while free > 0:
                job = _taken(stack, holding)

                if job is None:
                    break

                taken += 1

                # a job skipped as it starts takes no slot
                if self._start(job, relay):
                    free -= 1

        return taken

    def _max_jobs(self, stack: str, holding: list[int]) -> int:
        """The stack's slots, as the owner of the first job queued on it sees it."""
        first = (
            queue.in_turn(
                JobModel.objects.filter(stack=stack).exclude(owner_id__in=holding)
            )
            .select_related("owner")
            .first()
        )

        if first is None:
            return 0

        bench, _ = self._bench(first.owner.name)

        try:
            return bench.max_jobs(stack)
        except (BranchNotFoundError, AmbiguousBranchError):
            # its jobs are skipped as they start, one at a time
            return 1

    def _start(self, job: JobModel, relay: Relay[int]) -> bool:
        bench, scoring = self._bench(job.owner.name)

        try:
            trial = _trial(bench, job)
            sending = Sending(bench, trial, ConversationContext.WORKER, scoring)
        except UNSENT as e:
            _skipped(job, e)
            return False

        logger.info("%s", trial.description)
        relay.start(job.pk, sending.events())
        self._running[job.pk] = Running(job, sending)

        return True

    def _beat(self, relay: Relay[int]) -> None:
        """The jobs running beaten, their tallies written; a stop now heeded."""
        now = timezone.now()
        jobs: list[JobModel] = []

        for running in self._running.values():
            job, tokens = running.job, running.sending.tokens
            job.tokens, job.counted, job.beat = tokens.count, tokens.counted, now
            jobs.append(job)

        _ = JobModel.objects.bulk_update(jobs, ["tokens", "counted", "beat"])
        _ = WorkerStateModel.objects.filter(pk=1).update(seen=now)
        stopping = set(
            ControlsModel.objects.filter(
                owner_id__in={job.owner_id for job in jobs}, stopping=Stopping.NOW
            ).values_list("owner_id", flat=True)
        )

        for key, running in self._running.items():
            if running.job.owner_id in stopping and not running.stopped:
                running.stopped = True
                relay.stop(key)

    def _end(self, running: Running) -> None:
        """The job written down as its trial came out."""
        job, sending = running.job, running.sending
        # ended before it began, it is written down as stopped
        sending.stop()
        written = sending.written()
        run = written.run
        tokens = sending.tokens
        job.tokens, job.counted = tokens.count, tokens.counted
        job.run = run

        if run is None:
            _finished(job, Status.ERRORED, written.unrecorded or "nothing was sent")
        elif sending.outcome == STOPPED:
            _finished(job, Status.ABORTED, None)
        elif run.status == RunStatus.ERRORED:
            _finished(job, Status.ERRORED, written.unscored)
        else:
            _finished(job, Status.COMPLETED, written.unscored)

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
    """A stop from the host's service taken as Ctrl-C: the jobs written down."""

    def interrupted(_signal: int, _frame: FrameType | None) -> None:
        raise KeyboardInterrupt

    held = signal.signal(signal.SIGTERM, interrupted)

    try:
        yield
    finally:
        _ = signal.signal(signal.SIGTERM, held)


def _heeded(running: dict[int, Running]) -> None:
    """
    The worker seen at the queue, what lost its worker lost, and the stops
    heeded: an owner none of whose jobs runs any more stops no longer.
    """
    with transaction.atomic():
        state = WorkerStateModel.row(lock=True)
        state.seen = timezone.now()
        state.save(update_fields=["seen"])
        lost = queue.lose(sparing=running)

        if lost:
            logger.warning("%d job(s) lost with the worker that ran them", lost)

        _ = (
            ControlsModel.objects.exclude(stopping=Stopping.NO)
            .exclude(
                owner_id__in=JobModel.objects.filter(status=Status.RUNNING).values(
                    "owner_id"
                )
            )
            .update(stopping=Stopping.NO)
        )


def _taken(stack: str, holding: list[int]) -> JobModel | None:
    """The stack's next job in the queue, running, but for the owners holding."""
    with transaction.atomic():
        job = (
            queue.in_turn(
                JobModel.objects.select_for_update(skip_locked=True, of=("self",))
                .select_related("owner", "case_trail")
                .filter(stack=stack)
                .exclude(owner_id__in=holding)
            )
        ).first()

        if job is None:
            return None

        job.status = Status.RUNNING
        job.started = job.beat = timezone.now()
        job.save(update_fields=["status", "started", "beat"])

    return job


def _trial(bench: Bench, job: JobModel) -> Trial:
    """The trial as it was planned, its case's vignette as it was then."""
    cell = bench.cell_as_kept(job.kept)

    return Trial.of(bench.ready(cell), job.case_trail, job.case, job.seed)


def _skipped(job: JobModel, error: Exception) -> None:
    match error:
        case NotReady() | CellRefused():
            reason = "; ".join(reasons(error))
        case _:
            reason = str(error)

    logger.info("skipped: %s × %s: %s", job.cell, job.case, reason)
    _finished(job, Status.SKIPPED, reason)


def _finished(job: JobModel, status: Status, reason: str | None) -> None:
    job.status = status
    job.reason = reason
    job.finished = timezone.now()
    job.save(update_fields=["status", "reason", "tokens", "counted", "run", "finished"])


def _let_go() -> None:
    """A long-lived process's connections, let go where they went stale."""
    for connection in connections.all(initialized_only=True):
        if not connection.in_atomic_block:
            connection.close_if_unusable_or_obsolete()

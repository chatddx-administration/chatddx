# pyright: basic
"""
The worker's controls, as the repl's batch has them: a pause that lets the
case under way finish and holds the rest, and a stop that ends the drain,
once when the case under way is done, twice with it, written down as stopped.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from chatddx.worker import queue
from chatddx.worker.models import Stopping, WorkerStateModel

# seconds since the worker was last seen after which it isn't taken to be up
ALIVE = 10

# why a stop takes a case out of the queue
STOPPED = "stopped before its turn"


@dataclass(frozen=True)
class State:
    paused: bool
    stopping: Stopping
    seen: datetime | None

    @property
    def alive(self) -> bool:
        return self.seen is not None and timezone.now() - self.seen < timedelta(
            seconds=ALIVE
        )


def state() -> State:
    row = WorkerStateModel.row()
    return State(row.paused, Stopping(row.stopping), row.seen)


def pause() -> State:
    return _held(paused=True)


def resume() -> State:
    return _held(paused=False)


def stop() -> State:
    """
    Once, the drain ends when the case under way is done; twice, with it. With
    no case under way, what is queued is taken out now.
    """
    with transaction.atomic():
        row = WorkerStateModel.row(lock=True)

        if queue.running() is None:
            _ = queue.cancel(STOPPED)
            row.stopping = Stopping.NO
        else:
            row.stopping = min(row.stopping + 1, Stopping.NOW)

        row.save(update_fields=["stopping"])

    return state()


def _held(paused: bool) -> State:
    with transaction.atomic():
        row = WorkerStateModel.row(lock=True)
        row.paused = paused
        row.save(update_fields=["paused"])

    return state()

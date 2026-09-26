# pyright: basic
"""
An owner's controls, as the repl's batch has them: a pause that lets the
jobs running finish and holds the rest, and a stop that takes the owner's
queue out, once when their jobs running are done, twice with them, written
down as stopped. Each owner's are their own: others' jobs go on.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from chatddx.core.models import IdentityModel
from chatddx.worker import queue
from chatddx.worker.models import ControlsModel, Stopping, WorkerStateModel

# seconds since the worker was last seen after which it isn't taken to be up
ALIVE = 10

# why a stop takes a job out of the queue
STOPPED = "stopped before its turn"


@dataclass(frozen=True)
class State:
    """What an owner asked of the worker, and when the worker was last seen."""

    paused: bool
    stopping: Stopping
    seen: datetime | None

    @property
    def alive(self) -> bool:
        return self.seen is not None and timezone.now() - self.seen < timedelta(
            seconds=ALIVE
        )


def state(owner: str) -> State:
    controls = ControlsModel.of(_identity(owner))

    return State(
        controls.paused, Stopping(controls.stopping), WorkerStateModel.row().seen
    )


def pause(owner: str) -> State:
    return _held(owner, paused=True)


def resume(owner: str) -> State:
    return _held(owner, paused=False)


def stop(owner: str) -> State:
    """
    Once, the owner's queued jobs are taken out of the queue, and those
    running finish; twice, those running are stopped too. With none running,
    once is all it takes.
    """
    with transaction.atomic():
        controls = ControlsModel.of(_identity(owner), lock=True)
        _ = queue.stop(owner, STOPPED)

        if queue.running(owner):
            controls.stopping = min(controls.stopping + 1, Stopping.NOW)
        else:
            controls.stopping = Stopping.NO

        controls.save(update_fields=["stopping"])

    return state(owner)


def _held(owner: str, paused: bool) -> State:
    with transaction.atomic():
        controls = ControlsModel.of(_identity(owner), lock=True)
        controls.paused = paused
        controls.save(update_fields=["paused"])

    return state(owner)


def _identity(owner: str) -> IdentityModel:
    return IdentityModel.objects.get(name=owner)

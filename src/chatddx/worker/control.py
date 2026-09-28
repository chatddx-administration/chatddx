from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from chatddx.core.models import IdentityModel
from chatddx.worker import queue
from chatddx.worker.models import ControlsModel, Stopping, WorkerStateModel

ALIVE = 10

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

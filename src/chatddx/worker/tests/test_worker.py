from collections.abc import Callable
from datetime import timedelta
from typing import Any, cast

import pytest
from django.utils import timezone
from typer.testing import CliRunner

from chatddx.bench.bench import Bench
from chatddx.bench.plan import Plan, crossed
from chatddx.conftest import Stalling
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.entity_names import EntityName
from chatddx.worker import control, queue, worker
from chatddx.worker.models import QueuedModel, Status, Stopping, WorkerStateModel

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def beats(monkeypatch: pytest.MonkeyPatch) -> None:
    """Beats that come quickly, for tests that wait on one."""
    monkeypatch.setattr(worker, "BEAT", 0.01)


def planned(
    configuration: str = "free-text",
    tags: tuple[str, ...] = ("tag-2",),
    seed: int | None = 42,
    **variations: list[str],
) -> Plan:
    bench = Bench("alice")
    cell = bench.cell_of(configuration, "qwen3-8b-awq@fake")
    ticked = {
        entity: [
            bench.variation_named(cast(EntityName, entity), name) for name in names
        ]
        for entity, names in variations.items()
    }

    return Plan.of(bench, crossed(cell, ticked), tags, seed)


def queued() -> list[QueuedModel]:
    return list(QueuedModel.objects.select_related("run").order_by("pk"))


def pressing(times: int) -> Callable[..., Stopping]:
    """A beat that presses stop `times` at the first beat, as someone watching does."""
    beat = worker._beat  # pyright: ignore[reportPrivateUsage]
    pressed: list[bool] = []

    def pressed_beat(*args: Any) -> Stopping:
        if not pressed:
            pressed.append(True)

            for _ in range(times):
                _ = control.stop()

        return beat(*args)

    return pressed_beat


def test_the_worker_runs_the_queue_one_after_another_writing_each_down(
    fake: FakeTransport,
):
    assert queue.put("alice", planned()) == 2
    assert worker.run(fake) == 2

    first, second = queued()

    assert [(item.case, item.status) for item in (first, second)] == [
        ("case-1", Status.DONE),
        ("case-2", Status.DONE),
    ]
    assert first.run is not None and first.run.status == "completed"
    assert first.run.conversation is not None
    assert first.run.conversation.context == "worker"
    assert first.run.owner.name == "alice"
    assert first.counted and first.tokens > 0
    assert first.run.scores.exists()
    assert [request["seed"] for request in fake.requests] == [42, 42]
    assert control.state().alive


def test_a_paused_worker_takes_nothing_till_it_is_resumed(fake: FakeTransport):
    _ = queue.put("alice", planned())
    _ = control.pause()

    assert worker.run(fake) == 0
    assert {item.status for item in queued()} == {Status.QUEUED}

    _ = control.resume()

    assert worker.run(fake) == 2


def test_a_stop_with_no_case_under_way_takes_the_queue_out_at_once(
    fake: FakeTransport,
):
    _ = queue.put("alice", planned())

    assert control.stop().stopping == Stopping.NO
    assert {(item.status, item.reason) for item in queued()} == {
        (Status.CANCELLED, control.STOPPED)
    }
    assert worker.run(fake) == 0
    assert fake.requests == []


def test_a_stop_during_a_case_lets_it_finish_and_takes_the_rest_out(
    fake: FakeTransport, monkeypatch: pytest.MonkeyPatch
):
    _ = queue.put("alice", planned())
    monkeypatch.setattr(worker, "_beat", pressing(1))

    assert worker.run(fake) == 1

    first, second = queued()

    assert first.status == Status.DONE
    assert first.run is not None and first.run.status == "completed"
    assert second.status == Status.CANCELLED
    assert control.state().stopping == Stopping.NO


def test_stop_again_stops_the_case_under_way_too_written_down_stopped(
    stalling: Stalling, monkeypatch: pytest.MonkeyPatch
):
    _ = queue.put("alice", planned())
    monkeypatch.setattr(worker, "_beat", pressing(2))

    assert worker.run(stalling) == 1

    first, second = queued()

    assert first.status == Status.DONE
    assert first.run is not None
    assert (first.run.status, first.run.error) == ("errored", "stopped")
    assert stalling.aborted == stalling.requests
    assert second.status == Status.CANCELLED


def test_a_trial_that_can_t_be_sent_when_its_turn_comes_is_skipped_with_why(
    fake: FakeTransport,
):
    _ = queue.put("alice", planned())
    _ = QueuedModel.objects.filter(case="case-1").update(
        fingerprint="cddx-trail/1:sha256:0"
    )

    for stack in StackBranchModel.objects.filter(name="qwen3-8b-awq@fake"):
        stack.details = {**stack.details, "credential": "fake-key"}
        stack.save()

    assert worker.run(fake) == 2

    changed, secretless = queued()

    assert (changed.status, changed.reason) == (
        Status.SKIPPED,
        "free-text is another configuration than was planned",
    )
    assert (secretless.status, secretless.reason) == (
        Status.SKIPPED,
        "alice has no secret 'fake-key'",
    )
    assert fake.requests == []


def test_a_case_whose_worker_went_away_is_lost(fake: FakeTransport):
    _ = queue.put("alice", planned(tags=("tag-1",)))
    _ = QueuedModel.objects.update(
        status=Status.RUNNING, beat=timezone.now() - timedelta(minutes=5)
    )

    assert worker.run(fake) == 0

    [lost] = queued()

    assert (lost.status, lost.reason) == (
        Status.LOST,
        "the worker went away while it ran",
    )


def test_a_plan_joins_the_drain_under_way_or_begins_one(fake: FakeTransport):
    _ = queue.put("alice", planned(tags=("tag-1",)))
    _ = queue.put("alice", planned(tags=("tag-2",)))

    assert {item.drain for item in queued()} == {1}

    drain = queue.drain()

    assert drain is not None and (drain.total, drain.queued) == (3, 3)

    _ = worker.run(fake)
    _ = queue.put("alice", planned(tags=("tag-1",)))

    assert [item.drain for item in queued()] == [1, 1, 1, 2]
    assert queue.drain() == queue.Drain(
        total=1, queued=1, running=0, finished=0, cancelled=0
    )


def test_the_greedy_cells_of_a_plan_go_unseeded(fake: FakeTransport):
    _ = queue.put("alice", planned(tags=("tag-1",), sampling=["recommended", "greedy"]))
    _ = worker.run(fake)

    assert [(item.label, item.seed) for item in queued()] == [
        ("free-text", 42),
        ("free-text+sampling=greedy", None),
    ]
    assert ["seed" in request for request in fake.requests] == [True, False]


def test_the_latest_cases_come_last_one_first_with_their_scores(fake: FakeTransport):
    _ = queue.put("alice", planned())
    _ = worker.run(fake)

    latest = queue.latest()

    assert [item.case for item in latest] == ["case-2", "case-1"]
    assert all(item.run and item.run.scores.all() for item in latest)
    assert queue.running() is None


def test_the_host_s_service_runs_the_worker_as_it_did(
    fake: FakeTransport, monkeypatch: pytest.MonkeyPatch
):
    from chatddx.manage import app

    monkeypatch.setattr(worker, "TRANSPORT", fake)
    _ = queue.put("alice", planned())

    result = CliRunner().invoke(app, ["worker", "run"])

    assert result.exit_code == 0, result.output
    assert "2 cases taken from the queue" in result.output
    assert WorkerStateModel.objects.get().seen is not None

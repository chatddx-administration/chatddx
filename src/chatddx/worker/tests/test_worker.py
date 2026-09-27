import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any, cast, override
from uuid import UUID, uuid4

import pytest
from django.utils import timezone
from typer.testing import CliRunner

from chatddx.bench.bench import Bench, Drifted
from chatddx.bench.plan import Plan, crossed
from chatddx.conftest import Provision, Recommit, Stalling
from chatddx.core.utils import ensure_identity
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.repo.entities.stack.django import StackBranchModel
from chatddx.repo.entity_names import EntityName
from chatddx.repo.queries import head_of
from chatddx.repo.store.branch import get_branch_model
from chatddx.worker import control, queue, worker
from chatddx.worker.models import JobModel, Status, Stopping, WorkerStateModel

pytestmark = pytest.mark.django_db

FAKE = "qwen3-8b-awq@fake"

ARCHIVE = "archive"


@pytest.fixture(autouse=True)
def beats(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker, "BEAT", 0.01)
    monkeypatch.setattr(worker, "POLL", 0.01)


@pytest.fixture
def bob(provision: Provision) -> str:
    _ = provision(user="bob")
    return "bob"


class Slow(FakeTransport):
    @override
    async def next_token(self, generated: int, /) -> None:
        await asyncio.sleep(0.002)


def planned(
    owner: str = "alice",
    tags: tuple[str, ...] = ("tag-2",),
    seed: int | None = 42,
    **variations: list[str],
) -> Plan:
    bench = Bench(owner)
    cell = bench.cell_of("free-text", FAKE)
    ticked = {
        entity: [
            bench.variation_named(cast(EntityName, entity), name) for name in names
        ]
        for entity, names in variations.items()
    }

    return Plan.of(bench, crossed(cell, ticked), tags, seed)


def put(plan: Plan | None = None, owner: str = "alice", run: bool = True) -> UUID:
    plan = plan or planned(owner)
    batch = uuid4()
    _ = queue.put(owner, batch, plan.trials, run=run)

    return batch


def jobs(**filters: Any) -> list[JobModel]:
    return list(
        queue.with_read(JobModel.objects.filter(**filters))
        .select_related("run")
        .order_by("pk")
    )


def case_of(job: JobModel) -> str:
    return Bench(job.owner.name).name_of("case", job.trial.case)


def label_of(job: JobModel) -> str:
    return Bench(job.owner.name).label_of(job)


def stack_of(owner: str = ARCHIVE, stack: str = FAKE) -> StackBranchModel:
    head = head_of(StackBranchModel.objects.all(), owner, stack)
    assert head is not None

    return head


def slot(owner: str = ARCHIVE, stack: str = FAKE) -> queue.Slot:
    return queue.slot_of(stack_of(owner, stack))


def at_once(max_jobs: int, stack: str = FAKE) -> None:
    for model in StackBranchModel.objects.filter(name=stack):
        model.details = {**model.details, "max_jobs": max_jobs}
        model.save()


def restacked(
    owner: str, stack: str, trail: Any, like: StackBranchModel, **details: Any
) -> None:
    made = StackBranchModel.objects.create(
        owner=ensure_identity(owner),
        name=stack,
        trail=trail,
        details={**like.details, **details},
    )

    if like.owner_id == made.owner_id:
        made.collaborators.set(like.collaborators.all())


def beaten(
    monkeypatch: pytest.MonkeyPatch, then: Callable[[worker.Worker], None]
) -> list[int]:
    beat = worker.Worker._beat  # pyright: ignore[reportPrivateUsage]
    counted: list[int] = []

    def watched(self: worker.Worker, relay: Any) -> None:
        if not counted:
            then(self)

        counted.append(len(self._running))  # pyright: ignore[reportPrivateUsage]
        beat(self, relay)

    monkeypatch.setattr(worker.Worker, "_beat", watched)

    return counted


def stopping(times: int, owner: str = "alice") -> Callable[[worker.Worker], None]:
    def pressed(_worker: worker.Worker) -> None:
        for _press in range(times):
            _ = control.stop(owner)

    return pressed


def test_the_worker_runs_a_batch_s_jobs_writing_each_down(fake: FakeTransport):
    batch = put()

    assert worker.run(fake) == 2

    first, second = jobs()

    assert [(case_of(job), job.status, job.batch) for job in (first, second)] == [
        ("case-1", Status.COMPLETED, batch),
        ("case-2", Status.COMPLETED, batch),
    ]
    assert first.run is not None and first.run.status == "completed"
    assert first.run.trial_id == first.trial_id
    assert first.run.configuration_branch_id == first.configuration_branch_id
    assert first.run.stack_branch_id == first.stack_branch_id
    assert first.run.conversation is not None
    assert first.run.conversation.context == "worker"
    assert first.run.owner.name == "alice"
    assert first.counted and first.tokens > 0
    assert first.run.scores.exists()
    assert [request["seed"] for request in fake.requests] == [42, 42]
    assert control.state("alice").alive


@pytest.mark.parametrize("max_jobs", [1, 2, 4])
def test_jobs_run_side_by_side_as_many_as_their_stack_takes(
    max_jobs: int, monkeypatch: pytest.MonkeyPatch
):
    at_once(max_jobs)
    _ = put(planned(reasoning=["default", "off"]))
    counted = beaten(monkeypatch, lambda _: None)

    assert worker.run(Slow()) == 4
    assert max(counted) == max_jobs
    assert {job.status for job in jobs()} == {Status.COMPLETED}


def test_a_stack_s_slots_go_first_come_first_served_whosever_the_jobs(bob: str):
    at_once(1)
    _ = put(owner="alice")
    _ = put(planned(bob), owner=bob)

    assert queue.waiting(bob) == [
        queue.Waiting(slot(), FAKE, max_jobs=1, running=0, queued=2)
    ]
    assert queue.waiting("alice") == []

    _ = worker.run(FakeTransport())

    started = sorted(jobs(), key=lambda job: cast(Any, job.started))

    assert [(job.owner.name, case_of(job)) for job in started] == [
        ("alice", "case-1"),
        ("alice", "case-2"),
        (bob, "case-1"),
        (bob, "case-2"),
    ]


def test_a_stack_s_slots_are_its_own_timeline_s_whatever_its_name(
    bob: str, monkeypatch: pytest.MonkeyPatch
):
    at_once(1)
    archived = get_branch_model("stack", ARCHIVE, FAKE)
    restacked(bob, FAKE, archived.trail, like=stack_of(), max_jobs=2)
    _ = put(owner="alice")
    _ = put(planned(bob, reasoning=["default", "off"]), owner=bob)
    counted = beaten(monkeypatch, lambda _: None)

    assert (queue.slots(slot()), queue.slots(slot(bob))) == (1, 2)
    assert {job.stack_branch.owner.name for job in jobs(owner__name="alice")} == {
        ARCHIVE
    }
    assert {job.stack_branch.owner.name for job in jobs(owner__name=bob)} == {bob}
    assert queue.waiting("alice") == queue.waiting(bob) == []
    assert worker.run(Slow()) == 6
    assert max(counted) == 3


def test_the_slots_of_a_stack_are_its_head_s():
    assert queue.slots(slot()) == 4
    assert queue.slots(slot(ARCHIVE, "qwen3-8b-awq@pelle")) == 1

    at_once(2)

    assert queue.slots(slot()) == 2
    assert queue.slots((0, "nowhere@fake")) == 1


def test_an_owner_paused_waits_while_others_run_and_comes_before_no_one(
    fake: FakeTransport, bob: str
):
    _ = put(owner="alice")
    _ = put(planned(bob), owner=bob)
    _ = control.pause("alice")

    assert queue.waiting(bob) == []
    assert worker.run(fake) == 2
    assert {(job.owner.name, job.status) for job in jobs()} == {
        ("alice", Status.QUEUED),
        (bob, Status.COMPLETED),
    }

    _ = control.resume("alice")

    assert worker.run(fake) == 2


def test_a_stop_takes_the_owner_s_queue_out_at_once_and_no_one_else_s(
    fake: FakeTransport, bob: str
):
    _ = put(owner="alice")
    _ = put(planned(bob), owner=bob)

    assert control.stop("alice").stopping == Stopping.NO
    assert {(job.status, job.reason) for job in jobs(owner__name="alice")} == {
        (Status.STOPPED, control.STOPPED)
    }
    assert worker.run(fake) == 2
    assert {job.status for job in jobs(owner__name=bob)} == {Status.COMPLETED}
    assert [request["seed"] for request in fake.requests] == [42, 42]


def test_a_stop_as_a_job_runs_lets_it_finish_and_takes_the_rest_out(
    fake: FakeTransport, monkeypatch: pytest.MonkeyPatch
):
    at_once(1)
    _ = put()
    _ = beaten(monkeypatch, stopping(1))

    assert worker.run(fake) == 1

    first, second = jobs()

    assert first.status == Status.COMPLETED
    assert first.run is not None and first.run.status == "completed"
    assert second.status == Status.STOPPED
    assert control.state("alice").stopping == Stopping.NO


def test_stop_again_stops_the_jobs_running_too_written_down_stopped(
    stalling: Stalling, monkeypatch: pytest.MonkeyPatch
):
    at_once(1)
    _ = put()
    _ = beaten(monkeypatch, stopping(2))

    assert worker.run(stalling) == 1

    first, second = jobs()

    assert first.status == Status.ABORTED
    assert first.run is not None
    assert (first.run.status, first.run.error) == ("errored", "stopped")
    assert stalling.aborted == stalling.requests
    assert second.status == Status.STOPPED
    assert control.state("alice").stopping == Stopping.NO


def test_a_trial_that_can_t_be_sent_when_its_turn_comes_is_skipped_with_why(
    fake: FakeTransport,
):
    qwen = stack_of()
    other = get_branch_model("stack", ARCHIVE, "gpt-oss-20b@fake").trail
    _ = put(planned(tags=("tag-1",)))
    restacked(ARCHIVE, FAKE, other, like=qwen)
    _ = put(planned(tags=("tag-1",)))
    restacked(ARCHIVE, FAKE, other, like=qwen, credential="fake-key")

    with pytest.raises(Drifted, match=f"{FAKE} is another stack than was planned"):
        _ = Bench("alice").cell_read(jobs()[0])

    assert worker.run(fake) == 2

    drifted, secretless = jobs()

    assert (drifted.status, drifted.reason) == (
        Status.SKIPPED,
        f"{FAKE} is another stack than was planned",
    )
    assert (secretless.status, secretless.reason) == (
        Status.SKIPPED,
        "alice has no secret 'fake-key'",
    )
    assert fake.requests == []


def test_a_job_runs_the_trial_it_planned_whatever_its_names_come_to_mean(
    fake: FakeTransport, recommit: Recommit
):
    _ = put(planned(tags=("tag-1",), reasoning=["off"]))
    [job] = jobs()
    recommit("reasoning", "on", name="off")
    recommit("case", "case-2", name="case-1", tags=["tag-1"])

    assert (
        Bench("alice").described(job)
        == f"free-text+reasoning=off × {FAKE} × case-1 (seed 42)"
    )
    assert worker.run(fake) == 1

    [job] = jobs()
    [request] = fake.requests

    assert job.status == Status.COMPLETED
    assert request["chat_template_kwargs"] == {"enable_thinking": False}
    assert request["messages"][-1]["content"] == "case vignette 1"
    assert job.run is not None and job.run.trial_id == job.trial_id
    assert job.run.reasoning_branch_id == job.reasoning_branch_id
    assert job.run.reasoning_branch is not None
    assert job.run.reasoning_branch.trail.effort == "off"


def test_a_job_whose_worker_went_away_is_lost(fake: FakeTransport):
    _ = put(planned(tags=("tag-1",)))
    _ = JobModel.objects.update(
        status=Status.RUNNING, beat=timezone.now() - timedelta(minutes=5)
    )

    assert worker.run(fake) == 0

    [lost] = jobs()

    assert (lost.status, lost.reason) == (
        Status.LOST,
        "the worker went away while it ran",
    )


def test_a_batch_kept_for_later_runs_once_it_is_resumed(fake: FakeTransport):
    batch = put(run=False)

    assert {job.status for job in jobs()} == {Status.STORED}
    assert worker.run(fake) == 0
    assert queue.resume("alice", batch) == 2
    assert worker.run(fake) == 2
    assert {job.status for job in jobs()} == {Status.COMPLETED}


def test_a_batch_resumed_runs_what_didn_t_complete_and_rerun_all_of_it(
    fake: FakeTransport,
):
    batch = put()
    [kept, _] = jobs()
    _ = control.stop("alice")
    _ = JobModel.objects.filter(pk=kept.pk).update(status=Status.COMPLETED)

    assert queue.counts([batch]) == queue.Counts(total=2, completed=1, stopped=1)
    assert queue.resume("alice", batch) == 1
    assert worker.run(fake) == 1
    assert queue.resume("alice", batch) == 0

    runs = {job.pk: job.run_id for job in jobs()}

    assert queue.rerun("alice", batch) == 2
    assert queue.up_next("alice") == jobs()[0]
    assert queue.outstanding("alice") == 2
    assert worker.run(fake) == 2
    assert queue.counts([batch]) == queue.Counts(total=2, completed=2)
    assert all(job.run_id != runs[job.pk] for job in jobs())


def test_the_greedy_cells_of_a_plan_go_unseeded(fake: FakeTransport):
    _ = put(planned(tags=("tag-1",), sampling=["recommended", "greedy"]))
    _ = worker.run(fake)

    assert [(label_of(job), job.trial.seed) for job in jobs()] == [
        ("free-text", 42),
        ("free-text+sampling=greedy", None),
    ]
    assert sorted("seed" in request for request in fake.requests) == [False, True]


def test_the_latest_jobs_come_last_one_first_with_their_scores_the_owner_s(
    fake: FakeTransport, bob: str
):
    at_once(1)
    _ = put()
    _ = put(planned(bob, tags=("tag-1",)), owner=bob)
    _ = worker.run(fake)

    latest = queue.latest("alice")

    assert [case_of(job) for job in latest] == ["case-2", "case-1"]
    assert all(job.run and job.run.scores.all() for job in latest)
    assert [job.owner.name for job in queue.latest(bob)] == [bob]
    assert queue.running() == []


def test_the_host_s_service_runs_the_worker_as_it_did(
    fake: FakeTransport, monkeypatch: pytest.MonkeyPatch
):
    from chatddx.manage import app

    monkeypatch.setattr(worker, "TRANSPORT", fake)
    _ = put()

    result = CliRunner().invoke(app, ["worker", "run"])

    assert result.exit_code == 0, result.output
    assert "2 cases taken from the queue" in result.output
    assert WorkerStateModel.objects.get().seen is not None

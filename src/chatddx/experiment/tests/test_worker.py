from datetime import timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from django.utils import timezone

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.experiment import worker
from chatddx.experiment.models import ExperimentModel, RunModel
from chatddx.repo.base import BranchModel
from chatddx.repo.shufflers.expect import dump_expect_async
from chatddx.repo.shufflers.experiment import create_experiment_async
from chatddx.repo.shufflers.main import dump_trail_registry_async, ensure_identity_async
from chatddx.repo.trail_models import CaseTrailModel
from chatddx.utils import make_async

pytestmark = pytest.mark.django_db(transaction=True)


def _target(branch: BranchModel):
    return branch.target


target_async = make_async(_target)


@pytest_asyncio.fixture
async def owner():
    return await ensure_identity_async("alex")


@pytest_asyncio.fixture
async def stray_owner():
    """An identity with no branches of its own -- resolving a session's
    agent branch for a Run owned by this identity always comes up empty,
    which is what lets the "no branch found" path be tested without
    reaching the network."""
    return await ensure_identity_async("bob")


@pytest_asyncio.fixture
async def branches(owner: IdentityModel):
    path = Path(__file__).parent / "data/test-registry.toml"
    return await dump_trail_registry_async(path, owner.name)


def by_name(branches: dict[int, BranchModel], name: str) -> BranchModel:
    return next(branch for branch in branches.values() if branch.name == name)


@pytest_asyncio.fixture
async def case_1(branches: dict[str, dict[int, BranchModel]]) -> CaseTrailModel:
    return await target_async(by_name(branches["case"], "case-1"))


@pytest_asyncio.fixture
async def experiment(
    owner: IdentityModel,
    branches: dict[str, dict[int, BranchModel]],
    case_1: CaseTrailModel,
) -> ExperimentModel:
    # agent-2 merges in sampling_params-2, which fixes seed=0, so
    # create_experiment_async won't warn about a missing seed.
    agent = await target_async(by_name(branches["agent"], "agent-2"))

    _ = await dump_expect_async(
        case=case_1,
        scorer="",
        payload="the expected answer",
        owner_name=owner.name,
    )

    return await create_experiment_async(
        owner_name=owner.name,
        agent=agent,
        case=case_1,
        tags=None,
    )


async def queue_run(*, owner: IdentityModel, experiment: ExperimentModel) -> RunModel:
    return await RunModel.objects.acreate(
        owner=owner,
        experiment=experiment,
        status=RunStatusChoices.QUEUED,
    )


@pytest.mark.asyncio
async def test_execute_run_without_a_resolvable_branch_is_recorded_as_errored(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
):
    """`stray_owner` owns no branch of the experiment's agent, so execution
    fails before ever reaching the network -- and that failure still has to
    land on the Run as a status, per the worker's contract."""
    run = await queue_run(owner=stray_owner, experiment=experiment)

    await worker.execute_run(run.pk)

    await run.arefresh_from_db()
    assert run.status == RunStatusChoices.ERRORED
    assert run.session_id is None


@pytest.mark.asyncio
async def test_execute_run_skips_a_run_that_is_no_longer_queued(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
):
    """A Run already claimed (by a concurrent pass, or simply not queued in
    the first place) must be left untouched."""
    run = await queue_run(owner=stray_owner, experiment=experiment)
    run.status = RunStatusChoices.RUNNING
    await run.asave(update_fields=["status"])

    await worker.execute_run(run.pk)

    await run.arefresh_from_db()
    assert run.status == RunStatusChoices.RUNNING
    assert run.session_id is None


@pytest.mark.asyncio
async def test_process_queued_runs_only_picks_up_queued_runs(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
):
    queued_run = await queue_run(owner=stray_owner, experiment=experiment)
    stored_run = await RunModel.objects.acreate(
        owner=stray_owner,
        experiment=experiment,
        status=RunStatusChoices.STORED,
    )

    await worker.process_queued_runs()

    await queued_run.arefresh_from_db()
    await stored_run.arefresh_from_db()
    assert queued_run.status == RunStatusChoices.ERRORED
    assert stored_run.status == RunStatusChoices.STORED


@pytest.mark.asyncio
async def test_process_queued_runs_processes_oldest_first(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
    monkeypatch: pytest.MonkeyPatch,
):
    newer_run = await queue_run(owner=stray_owner, experiment=experiment)
    older_run = await queue_run(owner=stray_owner, experiment=experiment)

    now = timezone.now()
    await RunModel.objects.filter(pk=newer_run.pk).aupdate(timestamp=now)
    await RunModel.objects.filter(pk=older_run.pk).aupdate(
        timestamp=now - timedelta(hours=1)
    )

    processed: list[int] = []
    original_execute_run = worker.execute_run

    async def _tracking_execute_run(run_id: int) -> None:
        processed.append(run_id)
        await original_execute_run(run_id)

    monkeypatch.setattr(worker, "execute_run", _tracking_execute_run)

    await worker.process_queued_runs()

    assert processed == [older_run.pk, newer_run.pk]


async def complete_run(
    *, owner: IdentityModel, experiment: ExperimentModel
) -> RunModel:
    return await RunModel.objects.acreate(
        owner=owner,
        experiment=experiment,
        status=RunStatusChoices.COMPLETED,
    )


def _stub_scorer(run: RunModel) -> dict[str, int]:
    return {"run_id": run.pk}


async def _stub_async_scorer(run: RunModel) -> dict[str, bool]:
    return {"async": True}


def _broken_scorer(run: RunModel) -> None:
    raise RuntimeError("scoring blew up")


@pytest.mark.asyncio
async def test_score_run_with_no_scorer_configured_is_left_alone(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
):
    """`experiment` (see the fixture above) has no `scorer` set -- scoring
    it is a no-op, not an error."""
    run = await complete_run(owner=stray_owner, experiment=experiment)

    await worker.score_run(run.pk)

    await run.arefresh_from_db()
    assert run.status == RunStatusChoices.COMPLETED
    assert run.result is None


@pytest.mark.asyncio
async def test_score_run_stores_the_scorer_functions_return_value(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
):
    experiment.scorer = "chatddx.experiment.tests.test_worker._stub_scorer"
    await experiment.asave(update_fields=["scorer"])

    run = await complete_run(owner=stray_owner, experiment=experiment)

    await worker.score_run(run.pk)

    await run.arefresh_from_db()
    assert run.status == RunStatusChoices.SCORED
    assert run.result == {"run_id": run.pk}


@pytest.mark.asyncio
async def test_score_run_with_an_async_scorer_is_awaited(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
):
    experiment.scorer = "chatddx.experiment.tests.test_worker._stub_async_scorer"
    await experiment.asave(update_fields=["scorer"])

    run = await complete_run(owner=stray_owner, experiment=experiment)

    await worker.score_run(run.pk)

    await run.arefresh_from_db()
    assert run.status == RunStatusChoices.SCORED
    assert run.result == {"async": True}


@pytest.mark.asyncio
async def test_score_run_with_a_failing_scorer_is_recorded_as_errored(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
):
    experiment.scorer = "chatddx.experiment.tests.test_worker._broken_scorer"
    await experiment.asave(update_fields=["scorer"])

    run = await complete_run(owner=stray_owner, experiment=experiment)

    await worker.score_run(run.pk)

    await run.arefresh_from_db()
    assert run.status == RunStatusChoices.ERRORED


@pytest.mark.asyncio
async def test_score_run_skips_a_run_that_is_no_longer_completed(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
):
    experiment.scorer = "chatddx.experiment.tests.test_worker._stub_scorer"
    await experiment.asave(update_fields=["scorer"])

    run = await complete_run(owner=stray_owner, experiment=experiment)
    run.status = RunStatusChoices.ERRORED
    await run.asave(update_fields=["status"])

    await worker.score_run(run.pk)

    await run.arefresh_from_db()
    assert run.status == RunStatusChoices.ERRORED
    assert run.result is None


@pytest.mark.asyncio
async def test_process_completed_runs_only_picks_up_completed_runs(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
):
    experiment.scorer = "chatddx.experiment.tests.test_worker._stub_scorer"
    await experiment.asave(update_fields=["scorer"])

    completed_run = await complete_run(owner=stray_owner, experiment=experiment)
    queued_run = await RunModel.objects.acreate(
        owner=stray_owner,
        experiment=experiment,
        status=RunStatusChoices.QUEUED,
    )

    await worker.process_completed_runs()

    await completed_run.arefresh_from_db()
    await queued_run.arefresh_from_db()
    assert completed_run.status == RunStatusChoices.SCORED
    assert queued_run.status == RunStatusChoices.QUEUED


@pytest.mark.asyncio
async def test_process_completed_runs_processes_oldest_first(
    stray_owner: IdentityModel,
    experiment: ExperimentModel,
    monkeypatch: pytest.MonkeyPatch,
):
    newer_run = await complete_run(owner=stray_owner, experiment=experiment)
    older_run = await complete_run(owner=stray_owner, experiment=experiment)

    now = timezone.now()
    await RunModel.objects.filter(pk=newer_run.pk).aupdate(timestamp=now)
    await RunModel.objects.filter(pk=older_run.pk).aupdate(
        timestamp=now - timedelta(hours=1)
    )

    processed: list[int] = []
    original_score_run = worker.score_run

    async def _tracking_score_run(run_id: int) -> None:
        processed.append(run_id)
        await original_score_run(run_id)

    monkeypatch.setattr(worker, "score_run", _tracking_score_run)

    await worker.process_completed_runs()

    assert processed == [older_run.pk, newer_run.pk]

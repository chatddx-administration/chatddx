from dataclasses import dataclass
from typing import Any

import pytest
from asgiref.sync import sync_to_async
from django.db import connection, transaction

from chatddx.core import worker
from chatddx.core.choices import RunStatusChoices, SessionContextChoices
from chatddx.core.models import IdentityModel
from chatddx.core.tests.conftest import AGENT_OUTPUT, CASE_PAYLOAD
from chatddx.core.utils import ensure_identity
from chatddx.history.models import ExperimentModel, RunModel, SessionModel
from chatddx.history.schemas import SessionSpec
from chatddx.repo.entities.agent.django import AgentBranchModel
from chatddx.repo.entities.agent.pydantic import AgentTrailSpec
from chatddx.repo.entities.instruction.pydantic import InstructionTrailSchema
from chatddx.repo.families.pydantic import BranchSchemaDetails
from chatddx.repo.inventories import ParsedInventory
from chatddx.repo.shufflers.branch import commit

pytestmark = pytest.mark.django_db(transaction=True)


@dataclass
class StubResult:
    output: Any


class StubAgent:
    def __init__(self, output: Any = AGENT_OUTPUT, error: Exception | None = None):
        self.output: Any = output
        self.error: Exception | None = error
        self.prompts: list[str] = []
        self.sessions: list[SessionSpec] = []

    async def __call__(
        self,
        session: SessionSpec,
        prompt: str,
        agent_spec: AgentTrailSpec,
        **kwargs: Any,
    ) -> StubResult:
        self.prompts.append(prompt)
        self.sessions.append(session)

        if self.error:
            raise self.error

        return StubResult(output=self.output)


@pytest.fixture
def stub_agent(monkeypatch: pytest.MonkeyPatch) -> StubAgent:
    stub = StubAgent()
    monkeypatch.setattr(worker, "run_from_session", stub)
    return stub


@pytest.fixture(autouse=True)
def empty_queue():
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM pgqueuer")
    yield


def pending_passes() -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pgqueuer WHERE entrypoint = %s",
            [worker.ENTRYPOINT],
        )
        row = cursor.fetchone()

    assert row is not None
    return int(row[0])


def break_the_scorer(run_pk: int) -> None:
    run = RunModel.objects.select_related("experiment__expect__scorer").get(pk=run_pk)

    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE agents_scorer DISABLE TRIGGER USER")
        cursor.execute(
            "UPDATE agents_scorer SET command = %s WHERE id = %s",
            ["no_such_scorer", run.experiment.expect.scorer.pk],
        )
        cursor.execute("ALTER TABLE agents_scorer ENABLE TRIGGER USER")


apending_passes = sync_to_async(pending_passes)
abreak_the_scorer = sync_to_async(break_the_scorer)


@pytest.mark.asyncio
async def test_drain_runs_scores_and_records_a_queued_run(
    queued_run: RunModel,
    stub_agent: StubAgent,
):
    await worker.drain()

    assert stub_agent.prompts == [CASE_PAYLOAD]

    await queued_run.arefresh_from_db()
    assert queued_run.status == RunStatusChoices.SCORED
    assert queued_run.output == AGENT_OUTPUT
    assert queued_run.result == {
        "score": 100,
        "rank": 1,
        "matched": "community-acquired pneumonia",
        "expected": "pneumonia | copd | exacerbation & pulmonary",
    }

    session = await SessionModel.objects.aget(pk=queued_run.session_id)
    assert session.context == SessionContextChoices.EXPERIMENT
    assert str(queued_run.uuid) in (session.description or "")


@pytest.mark.asyncio
async def test_drain_leaves_the_queue_empty(
    queued_run: RunModel,
    stub_agent: StubAgent,
):
    _, _ = queued_run, stub_agent

    await worker.drain()

    assert await apending_passes() == 0


@pytest.mark.asyncio
async def test_drain_with_nothing_queued_is_a_no_op(stub_agent: StubAgent):
    await worker.drain()

    assert stub_agent.prompts == []


@pytest.mark.asyncio
async def test_a_stored_run_is_left_alone(
    queued_run: RunModel,
    stub_agent: StubAgent,
):
    queued_run.status = RunStatusChoices.STORED
    await queued_run.asave(update_fields=["status"])

    await worker.worker_pass()

    assert stub_agent.prompts == []
    await queued_run.arefresh_from_db()
    assert queued_run.status == RunStatusChoices.STORED


@pytest.mark.asyncio
async def test_a_run_another_pass_claimed_is_not_run_again(
    queued_run: RunModel,
    stub_agent: StubAgent,
):
    queued_run.status = RunStatusChoices.RUNNING
    await queued_run.asave(update_fields=["status"])

    await worker.execute_run(queued_run.pk)

    assert stub_agent.prompts == []
    await queued_run.arefresh_from_db()
    assert queued_run.status == RunStatusChoices.RUNNING


@pytest.mark.asyncio
async def test_a_failing_run_is_errored_not_retried_forever(
    queued_run: RunModel,
    monkeypatch: pytest.MonkeyPatch,
):
    stub = StubAgent(error=RuntimeError("the model is down"))
    monkeypatch.setattr(worker, "run_from_session", stub)

    await worker.worker_pass()

    await queued_run.arefresh_from_db()
    assert queued_run.status == RunStatusChoices.ERRORED
    assert queued_run.session_id is not None

    await worker.worker_pass()
    assert len(stub.prompts) == 1


@pytest.mark.asyncio
async def test_an_output_the_answer_is_missing_from_scores_zero(
    queued_run: RunModel,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(worker, "run_from_session", StubAgent(["nothing of note"]))

    await worker.worker_pass()

    await queued_run.arefresh_from_db()
    assert queued_run.status == RunStatusChoices.SCORED
    assert queued_run.result is not None
    assert queued_run.result["score"] == 0
    assert queued_run.result["rank"] is None


@pytest.mark.asyncio
async def test_an_output_further_down_the_list_scores_less(
    queued_run: RunModel,
    monkeypatch: pytest.MonkeyPatch,
):
    stub = StubAgent(["asthma", "bronchitis", "copd exacerbation"])
    monkeypatch.setattr(worker, "run_from_session", stub)

    await worker.worker_pass()

    await queued_run.arefresh_from_db()
    assert queued_run.result is not None
    assert queued_run.result["rank"] == 3
    assert queued_run.result["score"] == pytest.approx(100 / 3)


@pytest.mark.asyncio
async def test_an_output_its_scorer_cannot_read_errors_the_run_rather_than_scoring_0(
    queued_run: RunModel,
    monkeypatch: pytest.MonkeyPatch,
):
    # free text, where the scorer reads a list
    monkeypatch.setattr(worker, "run_from_session", StubAgent("pneumonia, likely"))

    await worker.worker_pass()

    await queued_run.arefresh_from_db()
    assert queued_run.status == RunStatusChoices.ERRORED
    assert queued_run.result is None
    # what came back is kept, so the mismatch can be seen
    assert queued_run.output == "pneumonia, likely"


@pytest.mark.asyncio
async def test_a_run_whose_scorer_does_not_exist_is_errored(
    queued_run: RunModel,
    stub_agent: StubAgent,
):
    _ = stub_agent
    await abreak_the_scorer(queued_run.pk)

    await worker.worker_pass()

    await queued_run.arefresh_from_db()
    assert queued_run.status == RunStatusChoices.ERRORED
    assert queued_run.session_id is not None


def archived_run(
    experiment: ExperimentModel,
    parsed_inventory: ParsedInventory,
    owner: IdentityModel,
    shared: bool,
) -> RunModel:
    """
    A queued run of an agent the owner holds no branch of: the archive's, the
    way a batch that builds agents from their parts would hold one -- shared
    with the owner, or not.
    """
    agent, _ = parsed_inventory.agent["diagnostician"]

    # a trail of its own, so no branch of the owner's points at it
    archived = agent.model_copy(
        update={"instruction": InstructionTrailSchema(definition="archived")},
    )

    _ = commit(
        trail=archived,
        branch_details=BranchSchemaDetails(
            name="archived diagnostician",
            owner="archive",
            collaborators=[owner.name] if shared else [],
        ),
    )

    branch = AgentBranchModel.objects.get(
        owner=ensure_identity("archive"),
        name="archived diagnostician",
    )

    assert not AgentBranchModel.objects.filter(
        owner=owner,
        target=branch.target,
    ).exists()

    return RunModel.objects.create(
        owner=owner,
        experiment=ExperimentModel.objects.create(
            owner=owner,
            agent=branch.target,
            case_id=experiment.case_id,
            expect_id=experiment.expect_id,
        ),
        status=RunStatusChoices.QUEUED,
    )


aarchived_run = sync_to_async(archived_run)


@pytest.mark.asyncio
async def test_an_agent_shared_with_the_run_owner_runs_under_the_shared_branch(
    experiment: ExperimentModel,
    parsed_inventory: ParsedInventory,
    owner: IdentityModel,
    stub_agent: StubAgent,
):
    run = await aarchived_run(experiment, parsed_inventory, owner, shared=True)

    await worker.worker_pass()

    await run.arefresh_from_db()
    assert run.status == RunStatusChoices.SCORED

    (session,) = stub_agent.sessions
    assert session.default_agent.name == "archived diagnostician"
    assert session.default_agent.owner.name == "archive"


@pytest.mark.asyncio
async def test_an_agent_the_run_owner_can_not_reach_errors_the_run(
    experiment: ExperimentModel,
    parsed_inventory: ParsedInventory,
    owner: IdentityModel,
    stub_agent: StubAgent,
):
    run = await aarchived_run(experiment, parsed_inventory, owner, shared=False)

    await worker.worker_pass()

    await run.arefresh_from_db()
    assert run.status == RunStatusChoices.ERRORED
    assert stub_agent.prompts == []


def test_wake_on_commit_enqueues_one_pass_after_the_transaction_lands():
    with transaction.atomic():
        worker.wake_on_commit()
        assert pending_passes() == 0

    assert pending_passes() == 1


def test_waking_twice_does_not_queue_two_passes():
    with transaction.atomic():
        worker.wake_on_commit()
        worker.wake_on_commit()

    assert pending_passes() == 1

import uuid
from typing import Any

import pytest
from asgiref.sync import sync_to_async
from django.db import connection, transaction
from django.utils import timezone
from pydantic_ai import ModelResponse, TextPart
from pydantic_core import to_jsonable_python

from chatddx.core import worker
from chatddx.core.choices import RoleChoices, RunStatusChoices, SessionContextChoices
from chatddx.core.tests.conftest import AGENT_REPLY, CASE_PAYLOAD
from chatddx.history.models import MessageModel, RunModel, SessionModel
from chatddx.history.schemas import SessionSpec
from chatddx.repo.entities.agent.pydantic import AgentTrailSpec

pytestmark = pytest.mark.django_db(transaction=True)


class StubAgent:
    """
    Stands in for `run_from_session`, which is the only part of a pass that
    talks to a model. Records what it was asked and leaves the reply behind as
    an assistant message, the way a real run would.
    """

    def __init__(self, reply: str = AGENT_REPLY, error: Exception | None = None):
        self.reply: str = reply
        self.error: Exception | None = error
        self.prompts: list[str] = []

    async def __call__(
        self,
        session: SessionSpec,
        prompt: str,
        agent_spec: AgentTrailSpec,
        **kwargs: Any,
    ) -> None:
        self.prompts.append(prompt)

        if self.error:
            raise self.error

        message = ModelResponse(parts=[TextPart(content=self.reply)])
        _ = await MessageModel.objects.acreate(
            agent_id=agent_spec.id,
            session_id=session.id,
            kind=message.kind,
            run_id=uuid.uuid4(),
            role=RoleChoices.ASSISTANT,
            payload=to_jsonable_python(message),
            timestamp=timezone.now(),
        )


@pytest.fixture
def stub_agent(monkeypatch: pytest.MonkeyPatch) -> StubAgent:
    stub = StubAgent()
    monkeypatch.setattr(worker, "run_from_session", stub)
    return stub


@pytest.fixture(autouse=True)
def empty_queue():
    """
    The pgqueuer tables aren't Django models, so nothing truncates them between
    tests the way it does the rest.
    """
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
    """
    Point a run's expectation at a command that resolves to nothing. Trails are
    immutable in the database, so this writes around the trigger that enforces
    it rather than going through the ORM.
    """
    run = RunModel.objects.select_related("experiment__expect__scorer").get(pk=run_pk)

    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE agents_scorer DISABLE TRIGGER USER")
        cursor.execute(
            "UPDATE agents_scorer SET command = %s WHERE id = %s",
            ["no_such_scorer", run.experiment.expect.scorer.pk],
        )
        cursor.execute("ALTER TABLE agents_scorer ENABLE TRIGGER USER")


# The database is off limits from an async test's own thread.
apending_passes = sync_to_async(pending_passes)
abreak_the_scorer = sync_to_async(break_the_scorer)


# A pass, end to end through pgqueuer


@pytest.mark.asyncio
async def test_drain_runs_scores_and_records_a_queued_run(
    queued_run: RunModel,
    stub_agent: StubAgent,
):
    await worker.drain()

    assert stub_agent.prompts == [CASE_PAYLOAD]

    await queued_run.arefresh_from_db()
    assert queued_run.status == RunStatusChoices.SCORED
    assert queued_run.result == {
        "score": 100,
        "matched_row": "pneumonia",
        "expected": "pneumonia\ncopd | (exacerbation & pulmonary)",
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


# What a pass does and doesn't pick up


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
    """The claim is a conditional UPDATE, so two passes can't both take a run."""
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
    # The session it got as far as opening is kept, so the failure is readable.
    assert queued_run.session_id is not None

    await worker.worker_pass()
    assert len(stub.prompts) == 1


# Scoring


@pytest.mark.asyncio
async def test_a_reply_that_misses_every_row_scores_zero(
    queued_run: RunModel,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(worker, "run_from_session", StubAgent(reply="nothing of note"))

    await worker.worker_pass()

    await queued_run.arefresh_from_db()
    assert queued_run.status == RunStatusChoices.SCORED
    assert queued_run.result is not None
    assert queued_run.result["score"] == 0
    assert queued_run.result["matched_row"] is None


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
    # The run itself completed; only the scoring of it failed.
    assert queued_run.session_id is not None


# Waking a running worker


def test_wake_on_commit_enqueues_one_pass_after_the_transaction_lands():
    with transaction.atomic():
        worker.wake_on_commit()
        # A pass that started here would look at the queue before the run
        # being queued is in it.
        assert pending_passes() == 0

    assert pending_passes() == 1


def test_waking_twice_does_not_queue_two_passes():
    with transaction.atomic():
        worker.wake_on_commit()
        worker.wake_on_commit()

    assert pending_passes() == 1

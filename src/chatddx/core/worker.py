# src/chatddx/core/worker.py
"""
The experiment worker.

`RunModel.status` is the queue: a run sits at `queued` until a worker pass
claims it, runs its experiment's agent over its case, and leaves it at
`completed`, then scores it and leaves it at `scored`. Postgres holds that
state, so a pass is safe to repeat and safe to run twice at once -- both
transitions are claimed with a conditional `UPDATE`.

Entry points:
    `wake`   -- ask a running worker for a pass (used by the admin).
    `drain`  -- one pass, then return (`chatddx worker run`).
    `serve`  -- process passes until killed (`chatddx worker serve`).
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from asgiref.sync import async_to_sync, sync_to_async
from django.db import close_old_connections, connections, transaction
from pgqueuer import PgQueuer
from pgqueuer.db import PsycopgDriver
from pgqueuer.domain.types import QueueExecutionMode
from pgqueuer.models import Job, Schedule

from chatddx.core.choices import RunStatusChoices, SessionContextChoices
from chatddx.django.portal.qs import qs_head
from chatddx.eval.scorers import resolve_scorer
from chatddx.history.models import ExperimentModel, RunModel
from chatddx.history.session import start_session
from chatddx.repo.entities.agent.django import AgentBranchModel
from chatddx.repo.entities.agent.pydantic import AgentTrailOut
from chatddx.repo.trail_cache import trail_cache
from chatddx.runtime.runners import run_from_session

logger = logging.getLogger(__name__)

ENTRYPOINT = "chatddx.process_queued_runs"
DEDUPE_KEY = "process_queued_runs"

# The safety net under `wake`: a run queued while no worker was listening, or
# one whose doorbell failed to ring, waits at most this long for a pass.
SWEEP_ENTRYPOINT = "chatddx.sweep_queued_runs"
SWEEP_EXPRESSION = "* * * * *"

_close_old_connections = sync_to_async(close_old_connections)


def _connection_kwargs() -> dict[str, Any]:
    settings_dict = connections["default"].settings_dict
    kwargs: dict[str, Any] = {"dbname": settings_dict["NAME"]}

    if settings_dict.get("USER"):
        kwargs["user"] = settings_dict["USER"]
    if settings_dict.get("PASSWORD"):
        kwargs["password"] = settings_dict["PASSWORD"]
    if settings_dict.get("HOST"):
        kwargs["host"] = settings_dict["HOST"]
    if settings_dict.get("PORT"):
        kwargs["port"] = settings_dict["PORT"]

    return kwargs


@asynccontextmanager
async def _connect() -> AsyncGenerator[psycopg.AsyncConnection]:
    """
    pgqueuer wants a connection of its own: it listens on a channel, which a
    connection Django is also using for the ORM can't do.
    """
    connection = await psycopg.AsyncConnection.connect(
        **_connection_kwargs(),
        autocommit=True,
    )
    try:
        yield connection
    finally:
        await connection.close()


def build_pgqueuer(connection: psycopg.AsyncConnection) -> PgQueuer:
    pgq = PgQueuer(PsycopgDriver(connection))

    @pgq.entrypoint(ENTRYPOINT)
    async def _process_queued_runs(job: Job) -> None:
        _ = job
        await worker_pass()

    @pgq.schedule(SWEEP_ENTRYPOINT, SWEEP_EXPRESSION)
    async def _sweep_queued_runs(schedule: Schedule) -> None:
        _ = schedule
        # Enqueue rather than run the pass here, so that a sweep and a `wake`
        # landing together still only cost one pass.
        await enqueue_pass(pgq)

    return pgq


async def enqueue_pass(pgq: PgQueuer) -> None:
    """
    Ask for a pass. `DEDUPE_KEY` keeps at most one pass waiting at a time, so
    ringing the doorbell a hundred times doesn't queue a hundred passes. A run
    queued while a pass is already running still gets one: the running pass
    holds the job at `picked`, which leaves the dedupe key free to take a
    `queued` one behind it.
    """
    assert pgq.queries is not None

    _ = await pgq.queries.enqueue(
        ENTRYPOINT,
        None,
        dedupe_key=DEDUPE_KEY,
        on_conflict="skip",
    )


async def worker_pass() -> None:
    """One trip through the queue: start what's queued, score what finished."""
    # Nothing closes this process's ORM connections for it the way the end of a
    # request does, so a pass starts by dropping any that went stale while the
    # worker sat idle.
    await _close_old_connections()

    try:
        await process_queued_runs()
        await process_completed_runs()
    finally:
        await _close_old_connections()


async def process_queued_runs() -> None:
    run_ids = [
        run_id
        async for run_id in (
            RunModel.objects.filter(status=RunStatusChoices.QUEUED)
            .order_by("timestamp")
            .values_list("id", flat=True)
        )
    ]

    if not run_ids:
        logger.debug("no queued runs to process")
        return

    logger.info("processing %d queued run(s)", len(run_ids))

    for run_id in run_ids:
        await execute_run(run_id)


async def execute_run(run_id: int) -> None:
    run = await RunModel.objects.select_related("owner").aget(pk=run_id)

    claimed = await RunModel.objects.filter(
        pk=run.pk, status=RunStatusChoices.QUEUED
    ).aupdate(status=RunStatusChoices.RUNNING)
    if not claimed:
        logger.debug("run %s already claimed by another pass", run.uuid)
        return

    logger.info("running run %s (experiment %s)", run.uuid, run.experiment_id)

    session_id: int | None = None

    try:
        experiment = await ExperimentModel.objects.select_related("case").aget(
            pk=run.experiment_id
        )

        agent_branch = await qs_head(
            AgentBranchModel.objects.filter(target_id=experiment.agent_id),
            run.owner.name,
        ).afirst()
        if agent_branch is None:
            raise RuntimeError(
                f"no branch of agent {experiment.agent_id} owned by "
                + f"{run.owner.name!r}: cannot start a session for run {run.uuid}"
            )

        session = await start_session(
            owner_id=run.owner_id,
            agent_id=agent_branch.pk,
            context=SessionContextChoices.EXPERIMENT,
            description=f"Session {run.uuid}",
        )
        session_id = session.id

        agent_spec = await trail_cache.get_async(AgentTrailOut, experiment.agent_id)

        _ = await run_from_session(
            session=session,
            prompt=experiment.case.payload,
            agent_spec=agent_spec,
        )

        run.status = RunStatusChoices.COMPLETED
        logger.info("run %s completed (session %s)", run.uuid, session_id)

    except Exception:
        logger.exception("run %s failed", run.uuid)
        run.status = RunStatusChoices.ERRORED

    finally:
        run.session_id = session_id
        await run.asave(update_fields=["session_id", "status"])


async def process_completed_runs() -> None:
    run_ids = [
        run_id
        async for run_id in (
            RunModel.objects.filter(status=RunStatusChoices.COMPLETED)
            .order_by("timestamp")
            .values_list("id", flat=True)
        )
    ]

    if not run_ids:
        logger.debug("no completed runs to score")
        return

    logger.info("scoring %d completed run(s)", len(run_ids))

    for run_id in run_ids:
        await score_run(run_id)


async def score_run(run_id: int) -> None:
    run = await RunModel.objects.select_related(
        "experiment", "experiment__expect", "experiment__expect__scorer"
    ).aget(pk=run_id)

    # An experiment doesn't pick a scorer of its own: how an expectation is
    # judged is part of the expectation.
    scorer_trail = run.experiment.expect.scorer

    logger.info("scoring run %s with %s", run.uuid, scorer_trail.command)

    result: Any = None

    try:
        scorer = resolve_scorer(scorer_trail.command)
        # A synchronous scorer goes through Django's own executor rather than a
        # thread of its own, so the ORM connections it opens are the ones
        # `worker_pass` closes at the end of the pass.
        result = (
            await scorer(run)
            if inspect.iscoroutinefunction(scorer)
            else await sync_to_async(scorer)(run)
        )
        status = RunStatusChoices.SCORED
        logger.info("run %s scored", run.uuid)

    except Exception:
        logger.exception("scoring run %s failed", run.uuid)
        status = RunStatusChoices.ERRORED

    _ = await RunModel.objects.filter(
        pk=run.pk, status=RunStatusChoices.COMPLETED
    ).aupdate(status=status, result=result)


async def wake() -> None:
    """
    Ask a running worker for a pass. Producers call this after queueing a run;
    it returns as soon as the request is on the queue, without waiting for the
    run itself. With no worker running, the request simply waits for one.
    """
    async with _connect() as connection:
        await enqueue_pass(build_pgqueuer(connection))


def wake_on_commit() -> None:
    """
    `wake` for producers in ordinary synchronous Django code, such as the
    admin. Two differences that both matter there:

    Deferred to commit, because a pass that starts before the run's
    transaction lands would look at the queue and see nothing.

    Best effort, because queueing a run is the part the user asked for. If the
    worker can't be reached the run stays queued and the next sweep starts it;
    that's a slower pass, not a lost one, and no reason to fail the request.
    """

    def _wake() -> None:
        try:
            async_to_sync(wake)()
        except Exception:
            logger.warning(
                "could not reach the worker: queued runs wait for the next sweep",
                exc_info=True,
            )

    transaction.on_commit(_wake)


async def drain() -> None:
    """One pass here and now, then return. Backs `chatddx worker run`."""
    logger.info("draining the run queue")

    async with _connect() as connection:
        pgq = build_pgqueuer(connection)
        await enqueue_pass(pgq)
        await pgq.qm.run(mode=QueueExecutionMode.drain)

    logger.info("run queue drained")


async def serve() -> None:
    """
    Process passes until killed. Backs `chatddx worker serve`, which is what a
    host runs as a service alongside Django.
    """
    logger.info("worker listening for runs")

    async with _connect() as connection:
        pgq = build_pgqueuer(connection)
        # Whatever was queued while no worker was up is waiting; don't make it
        # wait for the first sweep as well.
        await enqueue_pass(pgq)
        await pgq.run(mode=QueueExecutionMode.continuous)

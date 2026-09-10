from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from django.db import connections
from django.utils.module_loading import import_string
from pgqueuer import PgQueuer
from pgqueuer.db import PsycopgDriver
from pgqueuer.domain.types import QueueExecutionMode
from pgqueuer.models import Job

from chatddx.core.choices import RunStatusChoices
from chatddx.django.orm.qs import qs_canon
from chatddx.experiment.models import ExperimentModel, RunModel
from chatddx.history.session import start_session
from chatddx.repo.branch_models import AgentBranchModel
from chatddx.repo.trail_cache import trail_cache
from chatddx.repo.trail_specs import AgentSpec
from chatddx.runtime.runners import run_from_session

logger = logging.getLogger(__name__)

ENTRYPOINT = "chatddx.process_queued_runs"
DEDUPE_KEY = "process_queued_runs"


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
async def _connect() -> AsyncIterator[psycopg.AsyncConnection]:
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
        await process_queued_runs()
        await process_completed_runs()

    return pgq


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

        agent_branch = await qs_canon(
            AgentBranchModel.objects.filter(target_id=experiment.agent_id),
            run.owner.name,
        ).afirst()
        if agent_branch is None:
            raise RuntimeError(
                f"no branch of agent {experiment.agent_id} owned by "
                f"{run.owner.name!r}: cannot start a session for run {run.uuid}"
            )

        session = await start_session(
            owner_id=run.owner_id,
            agent_id=agent_branch.pk,
            description=f"Run {run.uuid}",
        )
        session_id = session.id

        agent_spec = await trail_cache.get_async(AgentSpec, experiment.agent_id)

        await run_from_session(
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
        "experiment", "experiment__expect", "experiment__scorer"
    ).aget(pk=run_id)

    scorer_trail = run.experiment.scorer
    if scorer_trail is None:
        logger.debug("run %s has no scorer configured: leaving unscored", run.uuid)
        return

    logger.info("scoring run %s with %s", run.uuid, scorer_trail.name)

    result: Any = None

    try:
        scorer = import_string(scorer_trail.name)
        result = (
            await scorer(run)
            if inspect.iscoroutinefunction(scorer)
            else await asyncio.to_thread(scorer, run)
        )
        status = RunStatusChoices.SCORED
        logger.info("run %s scored", run.uuid)

    except Exception:
        logger.exception("scoring run %s failed", run.uuid)
        status = RunStatusChoices.ERRORED

    _ = await RunModel.objects.filter(
        pk=run.pk, status=RunStatusChoices.COMPLETED
    ).aupdate(status=status, result=result)


async def trigger() -> None:
    logger.info("triggering worker pass")

    async with _connect() as connection:
        pgq = build_pgqueuer(connection)

        _ = await pgq.qm.queries.enqueue(
            ENTRYPOINT,
            None,
            dedupe_key=DEDUPE_KEY,
            on_conflict="skip",
        )

        await pgq.qm.run(mode=QueueExecutionMode.drain)

    logger.info("worker pass finished")

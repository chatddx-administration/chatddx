# pyright: basic
"""
Runs of the cell, as the repl's run and batch make them, streamed as
server-sent events. What the LLM sends back is streamed without the
database, from the server's loop or a loop of its own; a run is written down
in the request's thread. A client that goes away stops the run, written down
as stopped, and the batch.
"""

import asyncio
import json
import logging
import queue
import threading
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Iterator
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from django.utils import timezone
from ninja import Schema
from ninja.errors import HttpError
from ninja.responses import NinjaJSONEncoder
from pydantic import TypeAdapter
from pydantic_ai import (
    AgentRunResultEvent,
    AgentStreamEvent,
    PartDeltaEvent,
    PartStartEvent,
    ThinkingPart,
    ThinkingPartDelta,
)

from chatddx.bench.bench import Bench, Ready, Trial, drawn_seed
from chatddx.bench.cell import NONE, Cell
from chatddx.bench.outcome import STOPPED, failed, holds, unheeded
from chatddx.bench.plan import Plan, Planned
from chatddx.django.api.schemas import (
    Answered,
    Batched,
    BatchIn,
    Began,
    Event,
    Failed,
    Judged,
    Recorded,
    RunIn,
    Scored,
    Seed,
    Summarized,
)
from chatddx.django.api.showing import run_of, scores_of, sums_of, views_of
from chatddx.history.models import ConversationContext, RunModel, RunStatus, ScoreModel
from chatddx.history.record import Outcome
from chatddx.repo.entities.case.django import CaseTrailModel
from chatddx.repo.entities.case.pydantic import CaseTrailIn
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.repo.store.trail import dump_trail
from chatddx.runtime.run import Run, Runaway, invalid
from chatddx.scoring.score import Scoring

logger = logging.getLogger(__name__)

# pydantic-ai's events, streamed as they come
STREAMED: TypeAdapter[Any] = TypeAdapter(AgentStreamEvent)


def seed_of(ready: Ready, seed: Seed) -> int | None:
    """The seed given, or one drawn where none is and sampling isn't greedy."""
    if seed == NONE:
        return None

    if not ready.greedy:
        return drawn_seed() if seed is None else seed

    if seed is None:
        return None

    raise HttpError(
        422,
        "refused: seed: sampling is greedy (temperature 0), which ignores the"
        + ' seed: "seed": "none" runs it unseeded',
    )


class Sending:
    def __init__(self, bench: Bench, trial: Trial, scoring: Scoring | None = None):
        self.bench: Bench = bench
        self.trial: Trial = trial
        self.run: Run = bench.made(trial)
        self.scoring: Scoring | None = scoring

        self.outcome: Outcome | None = None
        self.started: datetime | None = None
        self.finished: datetime | None = None
        self.made: list[ScoreModel] = []

        self._thought: bool = False
        self._answer: Any = None
        self._written: bool = False

    @classmethod
    def of(cls, bench: Bench, cell: Cell, spec: RunIn) -> "Sending":
        # what stands in the way is answered with its error
        ready = bench.ready(cell)
        seed = seed_of(ready, spec.seed)

        if spec.case is not None:
            case = get_visible_branch_model("case", bench.identity, spec.case)
            trial = Trial.on(ready, case, seed)
        else:
            assert spec.vignette is not None
            # a vignette of the client's own is a case without a branch
            model = dump_trail(CaseTrailModel, CaseTrailIn(vignette=spec.vignette))
            called = bench.name_of("case", model)
            trial = Trial(ready, model.pk, called, spec.vignette, seed)

        try:
            return cls(bench, trial)
        except ValueError as e:
            raise HttpError(422, str(e)) from None

    def began(self) -> Began:
        return Began(
            run=UUID(self.run.run_id),
            description=self.trial.description,
            case=self.trial.called,
            seed=self.run.seed,
        )

    async def events(self) -> AsyncGenerator[Any]:
        """What the LLM sends back, then what its answer comes to: no database."""
        self.started = timezone.now()

        try:
            async with self.run.stream() as stream:
                async for event in stream:
                    match event:
                        case AgentRunResultEvent(result=result):
                            self._answer = result.output
                            yield Answered(answer=result.output, usage=result.usage)
                        case (
                            PartStartEvent(part=ThinkingPart())
                            | PartDeltaEvent(delta=ThinkingPartDelta())
                        ):
                            self._thought = True
                            yield event
                        case _:
                            yield event
        except (asyncio.CancelledError, GeneratorExit):
            self.outcome = STOPPED
            raise
        except Runaway as e:
            self.outcome = failed(e, self.run)
            yield self._judged(self.outcome, self.outcome.error)
        except Exception as e:  # noqa: BLE001
            self.outcome = failed(e, self.run)
            yield Failed(message=self.outcome.error or type(e).__name__)
        else:
            resolution = self.trial.ready.resolution
            self.outcome = Outcome(
                RunStatus.COMPLETED,
                answer=self._answer,
                valid=holds(resolution, self._answer),
            )
            yield self._judged(self.outcome)
        finally:
            self.finished = timezone.now()

    def _judged(self, outcome: Outcome, stopped: str | None = None) -> Judged:
        resolution = self.trial.ready.resolution
        coercion = resolution.coercion
        answer = outcome.answer

        return Judged(
            warning=unheeded(resolution.reasoning.intent, self._thought),
            valid=outcome.valid,
            problem=None if coercion is None else invalid(coercion.schema, answer),
            views=views_of(resolution.output, answer),
            stopped=stopped,
        )

    def recorded(self) -> list[Event]:
        """Write the run down, once, and score it; a run that never began isn't."""
        if self.outcome is None or self._written:
            return []

        self._written = True
        bench = self.bench

        try:
            recorded = bench.recorded(
                self.trial,
                self.run,
                self.outcome,
                self.started or timezone.now(),
                self.finished or timezone.now(),
                ConversationContext.API,
            )
        except Exception as e:
            logger.exception("a run of %s's was not recorded", bench.identity)
            return [Failed(message=f"not recorded: {type(e).__name__}: {e}")]

        said: list[Event] = []
        scoring = self.scoring or Scoring(bench.identity)

        try:
            self.made = scoring.score(recorded)
            said.append(Scored(scores=scores_of(self.made)))
        except Exception as e:
            logger.exception("run %s was not scored", recorded.uuid)
            said.append(Failed(message=f"not scored: {type(e).__name__}: {e}"))

        run = RunModel.objects.select_related(
            "trial__configuration__output", "conversation", "client"
        ).get(pk=recorded.pk)
        said.append(Recorded(run=run_of(run, scoring)))

        return said

    def through(self) -> Recorded:
        """Sent and recorded in one go, from a loop of its own."""

        async def sent() -> None:
            async for _ in self.events():
                pass

        try:
            asyncio.run(sent())
        finally:
            said = self.recorded()

        match said:
            case [*_, Recorded() as recorded]:
                return recorded
            case [Failed(message=message)]:
                raise HttpError(500, message)
            case _:
                raise HttpError(500, "the run was not recorded")


class Batch:
    def __init__(self, bench: Bench, cell: Cell, spec: BatchIn):
        # what stands in the way is answered with its error
        ready = bench.ready(cell)
        seed = seed_of(ready, spec.seed)
        plan = Plan(
            [Planned(cell, ready)], bench.cases(spec.tags), tuple(spec.tags), seed
        )

        if not plan.cases:
            raise HttpError(404, f"no case tagged {plan.tagged} for {bench.identity}")

        self.scoring: Scoring = Scoring(bench.identity)

        try:
            self.sendings: list[Sending] = [
                Sending(bench, trial, self.scoring) for trial in plan.trials
            ]
        except ValueError as e:
            raise HttpError(422, str(e)) from None

        self.batched: Batched = Batched(
            description=plan.description,
            cases=[case.name for case in plan.cases],
            seed=seed,
        )

    def summarized(self) -> list[Event]:
        made = [score for sending in self.sendings for score in sending.made]

        return [
            Summarized(
                runs=sum(sending.outcome is not None for sending in self.sendings),
                scorers=sums_of(self.scoring.summed(made)),
            )
        ]


class EventStream(StreamingHttpResponse):
    """Runs' events as they come: over ASGI from the server's loop, else their own."""

    def __init__(
        self,
        sendings: list[Sending],
        opening: list[Event] | None = None,
        closing: Callable[[], list[Event]] = list,
    ):
        self._sendings: list[Sending] = sendings
        self._opening: list[Event] = opening or []
        self._closing: Callable[[], list[Event]] = closing
        super().__init__(self._handed_over(), content_type="text/event-stream")
        self["Cache-Control"] = "no-cache"
        self["X-Accel-Buffering"] = "no"

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for event in self._opening:
            yield self.make_bytes(sse(event))

        for sending in self._sendings:
            yield self.make_bytes(sse(sending.began()))
            events = sending.events()

            try:
                async for event in events:
                    yield self.make_bytes(sse(event))
            except BaseException:
                # the client went away: the run stops, written down as stopped
                await events.aclose()
                await asyncio.shield(sync_to_async(sending.recorded)())
                raise

            for event in await sync_to_async(sending.recorded)():
                yield self.make_bytes(sse(event))

        for event in await sync_to_async(self._closing)():
            yield self.make_bytes(sse(event))

    def _handed_over(self) -> Iterator[bytes]:
        """Over WSGI, and to Django's test client."""
        for event in self._opening:
            yield self.make_bytes(sse(event))

        for sending in self._sendings:
            yield self.make_bytes(sse(sending.began()))

            handed: queue.Queue[Any] = queue.Queue()
            loop = asyncio.new_event_loop()
            task = loop.create_task(_hand_over(sending, handed))
            thread = threading.Thread(target=_send, args=(loop, task), daemon=True)
            thread.start()

            try:
                while (event := handed.get()) is not _DONE:
                    if isinstance(event, BaseException):
                        raise event

                    yield self.make_bytes(sse(event))
            except BaseException:
                # the client went away: the run stops, written down as stopped
                try:
                    loop.call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    pass  # it had ended, and its loop is closed

                thread.join()
                _ = sending.recorded()
                raise

            thread.join()

            for event in sending.recorded():
                yield self.make_bytes(sse(event))

        for event in self._closing():
            yield self.make_bytes(sse(event))


# what a run's thread hands over last
_DONE = object()


async def _hand_over(sending: Sending, handed: queue.Queue[Any]) -> None:
    try:
        async for event in sending.events():
            handed.put(event)
    except asyncio.CancelledError:
        pass
    except Exception as e:  # noqa: BLE001
        handed.put(e)
    finally:
        handed.put(_DONE)


def _send(loop: asyncio.AbstractEventLoop, task: asyncio.Task[None]) -> None:
    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        pass  # stopped before it began: nothing was sent
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def sse(event: Any) -> str:
    """An event of the API's own by its type, or of pydantic-ai's by its kind."""
    if isinstance(event, Schema):
        data = json.dumps(event.model_dump(), cls=NinjaJSONEncoder)
        return _sse(cast(Any, event).type, data)

    return _sse(event.event_kind, STREAMED.dump_json(event).decode())


def _sse(kind: str, data: str) -> str:
    return f"event: {kind}\ndata: {data}\n\n"

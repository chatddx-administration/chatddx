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
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Iterator
from contextlib import aclosing
from typing import Any, cast
from uuid import UUID

from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from ninja import Schema
from ninja.errors import HttpError
from ninja.responses import NinjaJSONEncoder
from pydantic import TypeAdapter
from pydantic_ai import AgentRunResultEvent, AgentStreamEvent

from chatddx.bench.bench import Bench, Ready, Trial, drawn_seed
from chatddx.bench.cell import NONE, Cell
from chatddx.bench.outcome import unheeded
from chatddx.bench.plan import Plan, Planned
from chatddx.bench.sending import Handed, Sending as BenchSending
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
from chatddx.history.models import ConversationContext, RunModel
from chatddx.history.record import Outcome
from chatddx.repo.entities.case.django import CaseTrailModel
from chatddx.repo.entities.case.pydantic import CaseTrailIn
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.repo.store.trail import dump_trail
from chatddx.runtime.run import Runaway, invalid
from chatddx.scoring.score import Scoring

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


class Sending(BenchSending):
    """A trial on its way, told in the API's events."""

    def __init__(self, bench: Bench, trial: Trial, scoring: Scoring | None = None):
        super().__init__(bench, trial, ConversationContext.API, scoring)
        self._told: bool = False

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
            trial = Trial.of(ready, model, called, seed)

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

    async def told(
        self,
    ) -> AsyncGenerator[AgentStreamEvent | Answered | Judged | Failed]:
        """What the LLM sends back, then what its answer comes to: no database."""
        async with aclosing(self.events()) as events:
            async for event in events:
                match event:
                    case AgentRunResultEvent(result=result):
                        yield Answered(answer=result.output, usage=result.usage)
                    case _:
                        yield event

        outcome = self.outcome
        assert outcome is not None

        match self.error:
            case None:
                yield self._judged(outcome)
            case Runaway():
                yield self._judged(outcome, outcome.error)
            case error:
                yield Failed(message=outcome.error or type(error).__name__)

    def _judged(self, outcome: Outcome, stopped: str | None = None) -> Judged:
        resolution = self.trial.ready.resolution
        coercion = resolution.coercion
        answer = outcome.answer

        return Judged(
            warning=unheeded(resolution.reasoning.intent, self.thought),
            valid=outcome.valid,
            problem=None if coercion is None else invalid(coercion.schema, answer),
            views=views_of(resolution.output, answer),
            stopped=stopped,
        )

    def recorded(self) -> list[Event]:
        """The run written down, once, and scored, as the API tells it."""
        if self.outcome is None or self._told:
            return []

        self._told = True
        written = self.written()

        if written.run is None:
            return [Failed(message=written.unrecorded)] if written.unrecorded else []

        said: list[Event] = [
            Failed(message=written.unscored)
            if written.unscored
            else Scored(scores=scores_of(written.scores))
        ]
        run = RunModel.objects.select_related(
            "trial__configuration__output", "conversation", "client"
        ).get(pk=written.run.pk)
        said.append(Recorded(run=run_of(run, self.scoring)))

        return said

    def through(self) -> Recorded:
        """Sent and recorded in one go, from a loop of its own."""

        async def sent() -> None:
            async for _ in self.told():
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
        made = [
            score for sending in self.sendings for score in sending.written().scores
        ]

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
            events = sending.told()

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

            try:
                with Handed(sending.told()) as handed:
                    for event in handed:
                        yield self.make_bytes(sse(event))
            except BaseException:
                # the client went away: the run stops, written down as stopped
                _ = sending.recorded()
                raise

            for event in sending.recorded():
                yield self.make_bytes(sse(event))

        for event in self._closing():
            yield self.make_bytes(sse(event))


def sse(event: Any) -> str:
    """An event of the API's own by its type, or of pydantic-ai's by its kind."""
    if isinstance(event, Schema):
        data = json.dumps(event.model_dump(), cls=NinjaJSONEncoder)
        return _sse(cast(Any, event).type, data)

    return _sse(event.event_kind, STREAMED.dump_json(event).decode())


def _sse(kind: str, data: str) -> str:
    return f"event: {kind}\ndata: {data}\n\n"

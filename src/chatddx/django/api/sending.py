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
from typing import Any
from uuid import UUID

from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from django.utils import timezone
from ninja.errors import HttpError
from ninja.responses import NinjaJSONEncoder
from pydantic_ai import (
    AgentRunResultEvent,
    FunctionToolResultEvent,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    ToolCallPart,
    ToolCallPartDelta,
    ToolReturnPart,
)

from chatddx.django.api.schemas import (
    Batched,
    BatchIn,
    Began,
    Called,
    Event,
    Failed,
    Judged,
    Recorded,
    Returned,
    RunIn,
    Scored,
    Seed,
    Summarized,
    Thought,
    Used,
    Viewed,
    Warned,
    Wrote,
)
from chatddx.django.api.showing import run_of, scores_of, sums_of, views_of
from chatddx.history.models import (
    ConversationContext,
    MessageKind,
    MessageModel,
    RunModel,
    RunStatus,
    ScoreModel,
)
from chatddx.history.record import Outcome
from chatddx.repl.bench import (
    SHARED_BY,
    STOPPED,
    Bench,
    Ready,
    drawn_seed,
    failed,
    greedy,
    unheeded,
)
from chatddx.repl.cell import NONE
from chatddx.repo.entities.case.django import CaseTrailModel
from chatddx.repo.entities.case.pydantic import CaseTrailIn
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.repo.store.trail import dump_trail
from chatddx.runtime.run import FINAL_RESULT, Run, invalid
from chatddx.scoring.score import Scoring

logger = logging.getLogger(__name__)


def ready_of(bench: Bench) -> Ready:
    """What stands in the way of a run of the cell, as the error it is answered with."""
    cell = bench.cell

    if not (cell.configuration and cell.stack):
        raise HttpError(400, "the cell needs a configuration and a stack")

    owner = cell.configuration.owner.name

    if owner not in (bench.identity, SHARED_BY["configuration"]):
        raise HttpError(403, f"{cell.name} is {owner}'s: save it as your own first")

    # a refused cell is answered with its refusals
    resolution = bench.resolve()
    api_key = bench.secret(resolution.credential)

    if resolution.credential and api_key is None:
        raise HttpError(
            409, f"{bench.identity} has no secret '{resolution.credential}'"
        )

    return Ready(resolution, api_key, bench.tools())


def seed_of(ready: Ready, seed: Seed) -> int | None:
    """The seed given, or one drawn where none is and sampling isn't greedy."""
    if seed == NONE:
        return None

    if not greedy(ready.resolution.sampling):
        return drawn_seed() if seed is None else seed

    if seed is None:
        return None

    raise HttpError(
        422,
        "refused: seed: sampling is greedy (temperature 0), which ignores the"
        + ' seed: "seed": "none" runs it unseeded',
    )


class Sending:
    def __init__(
        self,
        bench: Bench,
        ready: Ready,
        case: int,
        called: str,
        vignette: str,
        seed: int | None,
        scoring: Scoring | None = None,
    ):
        self.bench: Bench = bench
        self.ready: Ready = ready
        self.case: int = case
        self.called: str = called
        self.run: Run = bench.made(ready, vignette, seed)
        self.description: str = bench.described(called, seed)
        self.scoring: Scoring | None = scoring

        self.outcome: Outcome | None = None
        self.started: datetime | None = None
        self.finished: datetime | None = None
        self.made: list[ScoreModel] = []

        # each part pydantic-ai is sending, by its index in its response: its
        # number through the run, what it is, and whether it came in content
        self._parts: dict[int, tuple[int, str, bool]] = {}
        self._begun: int = 0
        self._thought: bool = False
        self._answer: Any = None
        self._written: bool = False

    @classmethod
    def of(cls, bench: Bench, spec: RunIn) -> "Sending":
        ready = ready_of(bench)
        seed = seed_of(ready, spec.seed)

        if spec.case is not None:
            case = get_visible_branch_model("case", bench.identity, spec.case)
            trail, called, vignette = case.trail_id, case.name, case.trail.vignette
        else:
            assert spec.vignette is not None
            vignette = spec.vignette
            # a vignette of the client's own is a case without a branch
            model = dump_trail(CaseTrailModel, CaseTrailIn(vignette=vignette))
            trail, called = model.pk, bench.name_of("case", model)

        try:
            return cls(bench, ready, trail, called, vignette, seed)
        except ValueError as e:
            raise HttpError(422, str(e)) from None

    def began(self) -> Began:
        return Began(
            run=UUID(self.run.run_id),
            description=self.description,
            case=self.called,
            seed=self.run.seed,
        )

    async def events(self) -> AsyncGenerator[Event]:
        """What the LLM sends back, then what its answer comes to: no database."""
        self.started = timezone.now()

        try:
            async with self.run.stream() as stream:
                async for event in stream:
                    for said in self._said(event):
                        yield said
        except (asyncio.CancelledError, GeneratorExit):
            self.outcome = STOPPED
            raise
        except Exception as e:  # noqa: BLE001
            self.outcome = failed(e, self.ready.resolution)
            yield Failed(message=self.outcome.error or type(e).__name__)
        else:
            for judged in self._judged():
                yield judged
        finally:
            self.finished = timezone.now()

    def _judged(self) -> list[Event]:
        resolution = self.ready.resolution
        answer = self._answer
        self.outcome = Outcome(RunStatus.COMPLETED, answer=answer)
        judged: list[Event] = []
        warning = unheeded(resolution.reasoning.intent, self._thought)

        if warning is not None:
            judged.append(Warned(message=warning))

        if resolution.coercion is not None:
            problem = invalid(resolution.coercion.schema, answer)
            self.outcome = Outcome(
                RunStatus.COMPLETED, answer=answer, valid=problem is None
            )
            judged.append(Judged(valid=problem is None, problem=problem))

        judged.append(Viewed(views=views_of(resolution.output, answer)))

        return judged

    def _said(self, event: Any) -> list[Event]:
        match event:
            case PartStartEvent(
                index=index, part=ThinkingPart(content=text, id=origin)
            ):
                self._thought = True
                part = self._begin(index, "thinking", origin == "content")
                return [Thought(part=part, text=text, in_content=origin == "content")]
            case PartDeltaEvent(
                index=index, delta=ThinkingPartDelta(content_delta=text)
            ) if text:
                self._thought = True
                part, _, in_content = self._part(index, "thinking")
                return [Thought(part=part, text=text, in_content=in_content)]
            case PartStartEvent(index=index, part=TextPart(content=text)):
                return [Wrote(part=self._begin(index, "text"), text=text)]
            case PartDeltaEvent(
                index=index, delta=TextPartDelta(content_delta=text)
            ) if text:
                return [Wrote(part=self._part(index, "text")[0], text=text)]
            case PartStartEvent(
                index=index, part=ToolCallPart(tool_name=name, args=args)
            ):
                return [
                    Called(
                        part=self._begin(index, name), tool=name, arguments=_sent(args)
                    )
                ]
            case PartDeltaEvent(
                index=index, delta=ToolCallPartDelta(args_delta=args)
            ) if args:
                part, tool, _ = self._part(index, "")
                return [Called(part=part, tool=tool, arguments=_sent(args))]
            case FunctionToolResultEvent(part=ToolReturnPart() as returned):
                return [
                    Returned(
                        tool=returned.tool_name, content=returned.model_response_str()
                    )
                ]
            case AgentRunResultEvent(result=result):
                self._answer = result.output
                usage = result.usage
                return [
                    Used(
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        requests=usage.requests,
                    )
                ]
            case _:
                return []

    def _begin(self, index: int, kind: str, in_content: bool = False) -> int:
        """A part begun, numbered through the run, not afresh in each response."""
        part = self._begun
        self._begun += 1
        self._parts[index] = (part, kind, in_content)
        return part

    def _part(self, index: int, kind: str) -> tuple[int, str, bool]:
        if index not in self._parts:
            _ = self._begin(index, kind)

        return self._parts[index]

    def recorded(self) -> list[Event]:
        """Write the run down, once, and score it; a run that never began isn't."""
        if self.outcome is None or self._written:
            return []

        self._written = True
        bench = self.bench

        try:
            recorded = bench.recorded(
                self.ready,
                self.case,
                self.run,
                self.outcome,
                self.started or timezone.now(),
                self.finished or timezone.now(),
                self.description,
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
        said.append(Recorded(run=run_of(bench, run, scoring)))

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
    def __init__(self, bench: Bench, spec: BatchIn):
        ready = ready_of(bench)
        seed = seed_of(ready, spec.seed)
        tagged = " or ".join(spec.tags)
        cases = bench.cases(spec.tags)

        if not cases:
            raise HttpError(404, f"no case tagged {tagged} for {bench.identity}")

        cell = bench.cell
        assert cell.stack
        self.scoring: Scoring = Scoring(bench.identity)

        try:
            self.sendings: list[Sending] = [
                Sending(
                    bench,
                    ready,
                    case.trail_id,
                    case.name,
                    case.trail.vignette,
                    seed,
                    self.scoring,
                )
                for case in cases
            ]
        except ValueError as e:
            raise HttpError(422, str(e)) from None

        many = "s" if len(cases) > 1 else ""
        self.batched: Batched = Batched(
            description=f"{cell.label} × {cell.stack.name} × {len(cases)} case{many}"
            + f" tagged {tagged}",
            cases=[case.name for case in cases],
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


def sse(event: Event) -> str:
    data = json.dumps(event.model_dump(), cls=NinjaJSONEncoder)
    return f"event: {event.type}\ndata: {data}\n\n"


def transcript(bench: Bench, run: RunModel, scoring: Scoring) -> list[Event]:
    """A recorded run again, as it streamed, but for what the answer's tool returned."""
    stored = list(
        MessageModel.objects.filter(conversation=run.conversation, run_uuid=run.uuid)
    )
    messages = ModelMessagesTypeAdapter.validate_python(
        [message.payload for message in stored if message.kind != MessageKind.ERROR]
    )
    said: list[Event] = [
        Began(
            run=run.uuid,
            description=(run.conversation.description if run.conversation else None)
            or "",
            case=bench.name_of("case", run.trial.case),
            seed=run.trial.seed,
        )
    ]
    begun = 0

    for message in messages:
        match message:
            case ModelResponse(parts=parts):
                for part in parts:
                    match part:
                        case ThinkingPart(content=text, id=origin):
                            said.append(
                                Thought(
                                    part=begun,
                                    text=text,
                                    in_content=origin == "content",
                                )
                            )
                        case TextPart(content=text):
                            said.append(Wrote(part=begun, text=text))
                        case ToolCallPart(tool_name=name):
                            said.append(
                                Called(
                                    part=begun,
                                    tool=name,
                                    arguments=part.args_as_json_str(),
                                )
                            )
                        case _:
                            continue

                    begun += 1
            case ModelRequest(parts=parts):
                for part in parts:
                    if (
                        isinstance(part, ToolReturnPart)
                        and part.tool_name != FINAL_RESULT
                    ):
                        said.append(
                            Returned(
                                tool=part.tool_name, content=part.model_response_str()
                            )
                        )

    answered = run.answer is not None
    responses = [message for message in messages if isinstance(message, ModelResponse)]

    if answered:
        said.append(
            Used(
                input_tokens=sum(response.usage.input_tokens for response in responses),
                output_tokens=sum(
                    response.usage.output_tokens for response in responses
                ),
                requests=len(responses),
            )
        )

    for message in stored:
        if message.kind == MessageKind.ERROR:
            said.append(Failed(message=str(message.payload["error"])))

    if answered:
        output = scoring.output_of(run)

        if run.valid is not None and output.json_schema is not None:
            problem = invalid(output.json_schema, run.answer)
            said.append(Judged(valid=problem is None, problem=problem))

        said.append(Viewed(views=views_of(output, run.answer)))

    said.append(Scored(scores=scores_of(scoring.latest(run))))

    return said


def _sent(arguments: Any) -> str:
    """A call's arguments, or a piece of them, as they were sent."""
    match arguments:
        case str():
            return arguments
        case None:
            return ""
        case _:
            return json.dumps(arguments)

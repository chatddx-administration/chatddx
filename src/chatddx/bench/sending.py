"""
A trial on its way, as the repl, the API and the worker send one: sent,
streamed back, come to an outcome, written down once and scored. The stream
touches no database, so a caller whose database is its thread's takes it
in a thread of its own (Handed).
"""

import asyncio
import logging
import queue
import threading
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Self, override

from django.utils import timezone
from pydantic_ai import (
    AgentRunResultEvent,
    AgentStreamEvent,
    PartDeltaEvent,
    PartStartEvent,
    ThinkingPart,
    ThinkingPartDelta,
)

from chatddx.bench.bench import Bench, Trial
from chatddx.bench.outcome import STOPPED, failed, holds
from chatddx.history.models import ConversationContext, RunModel, RunStatus, ScoreModel
from chatddx.history.record import Outcome
from chatddx.runtime.run import Run
from chatddx.scoring.score import Scoring

logger = logging.getLogger(__name__)

# what the LLM sends back, as pydantic-ai streams it, and what it came to
type LLMEvent = AgentStreamEvent | AgentRunResultEvent[Any]


@dataclass
class Tokens:
    """
    What the LLM has written so far, as the repl's batch tallies it: a token
    an event, till the server says how many.
    """

    count: int = 0
    # the count the server gave
    counted: bool = False

    def heard(self, event: LLMEvent) -> None:
        match event:
            case PartStartEvent() | PartDeltaEvent() if not self.counted:
                self.count += 1
            case AgentRunResultEvent(result=result):
                self.count = result.usage.output_tokens
                self.counted = True
            case _:
                pass

    @override
    def __str__(self) -> str:
        return str(self.count) if self.counted or not self.count else f"~{self.count}"


@dataclass(frozen=True)
class Written:
    """The run as it was written down and scored, or why it wasn't."""

    run: RunModel | None = None
    scores: list[ScoreModel] = field(default_factory=list[ScoreModel])
    unrecorded: str | None = None
    unscored: str | None = None


class Sending:
    def __init__(
        self,
        bench: Bench,
        trial: Trial,
        context: ConversationContext,
        scoring: Scoring | None = None,
    ):
        self.bench: Bench = bench
        self.trial: Trial = trial
        self.context: ConversationContext = context
        # a ValueError where the run can't be made, a tool that won't load
        self.run: Run = bench.made(trial)

        self.outcome: Outcome | None = None
        # what the stream failed with, if it did
        self.error: Exception | None = None
        self.answer: Any = None
        self.thought: bool = False
        self.tokens: Tokens = Tokens()
        self.started: datetime | None = None
        self.finished: datetime | None = None

        self._scoring: Scoring | None = scoring
        self._written: Written | None = None

    @property
    def scoring(self) -> Scoring:
        if self._scoring is None:
            self._scoring = Scoring(self.bench.identity)

        return self._scoring

    async def events(self) -> AsyncGenerator[LLMEvent]:
        """What the LLM sends back, as it comes; what it came to, after."""
        self.started = timezone.now()

        try:
            async with self.run.stream() as stream:
                async for event in stream:
                    match event:
                        case AgentRunResultEvent(result=result):
                            self.answer = result.output
                        case (
                            PartStartEvent(part=ThinkingPart())
                            | PartDeltaEvent(delta=ThinkingPartDelta())
                        ):
                            self.thought = True
                        case _:
                            pass

                    self.tokens.heard(event)
                    yield event
        except (asyncio.CancelledError, GeneratorExit):
            self.outcome = STOPPED
            raise
        except Exception as e:  # noqa: BLE001
            self.error = e
            self.outcome = failed(e, self.run)
        else:
            self.outcome = Outcome(
                RunStatus.COMPLETED,
                answer=self.answer,
                valid=holds(self.trial.ready.resolution, self.answer),
            )
        finally:
            self.finished = timezone.now()

    def stop(self) -> None:
        """Stopped before it came to anything: written down as stopped."""
        if self.outcome is None:
            self.outcome = STOPPED

    def written(self) -> Written:
        """The run written down, once, and scored; a run that never began isn't."""
        if self._written is not None:
            return self._written

        if self.outcome is None:
            return Written()

        bench = self.bench

        try:
            recorded = bench.recorded(
                self.trial,
                self.run,
                self.outcome,
                self.started or timezone.now(),
                self.finished or timezone.now(),
                self.context,
            )
        except Exception as e:
            logger.exception("a run of %s's was not recorded", bench.identity)
            self._written = Written(unrecorded=f"not recorded: {type(e).__name__}: {e}")
            return self._written

        try:
            scores = self.scoring.score(recorded)
        except Exception as e:
            logger.exception("run %s was not scored", recorded.uuid)
            self._written = Written(
                recorded, unscored=f"not scored: {type(e).__name__}: {e}"
            )
        else:
            self._written = Written(recorded, scores)

        return self._written


# what comes of a handed stream in place of an event where none came a while
TICK: Any = object()

# what a stream's thread hands over last
_DONE: Any = object()


class Handed:
    """
    An async stream taken in a thread and a loop of its own, its events
    handed over to the caller's thread as they come, so that the caller's
    database stays its own: over WSGI, to Django's test client, and to the
    worker. Where nothing came for `tick` seconds, a TICK comes instead.
    """

    def __init__(self, events: AsyncIterator[Any], tick: float | None = None):
        self._tick: float | None = tick
        self._handed: queue.Queue[Any] = queue.Queue()
        self._done: bool = False
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._task: asyncio.Task[None] = self._loop.create_task(
            _hand_over(events, self._handed)
        )
        self._thread: threading.Thread = threading.Thread(
            target=_send, args=(self._loop, self._task, self._handed), daemon=True
        )
        self._thread.start()

    def __iter__(self) -> Iterator[Any]:
        while not self._done:
            try:
                event = self._handed.get(timeout=self._tick)
            except queue.Empty:
                yield TICK
                continue

            if event is _DONE:
                self._done = True
            elif isinstance(event, BaseException):
                raise event
            else:
                yield event

    def stop(self) -> None:
        """Stop the stream where it is: its events end with what came."""
        try:
            _ = self._loop.call_soon_threadsafe(self._task.cancel)
        except RuntimeError:
            pass  # it had ended, and its loop is closed

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        # a caller that goes away before the stream ends takes it along
        if not self._done:
            self.stop()

        self._thread.join()


async def _hand_over(events: AsyncIterator[Any], handed: queue.Queue[Any]) -> None:
    try:
        async for event in events:
            handed.put(event)
    except asyncio.CancelledError:
        pass
    except Exception as e:  # noqa: BLE001
        handed.put(e)


def _send(
    loop: asyncio.AbstractEventLoop,
    task: asyncio.Task[None],
    handed: queue.Queue[Any],
) -> None:
    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        pass  # stopped before it began: nothing was sent
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        handed.put(_DONE)

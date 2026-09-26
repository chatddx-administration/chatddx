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
from collections.abc import AsyncGenerator, AsyncIterator, Hashable, Iterator
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

# what a relay hands over for a stream last, once its task has ended
ENDED: Any = object()


class Relay[K: Hashable]:
    """
    Async streams, each a task of one loop in a thread of its own, their
    events handed over to the caller's thread as they come, each with its
    stream's key, so that the caller's database stays its own: over WSGI, to
    Django's test client, and to the worker, a stream a job it runs. A
    stream's last is ENDED, once its task is done: stopped, it has gone its
    way by then, written down its outcome included.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._handed: queue.Queue[tuple[K, Any]] = queue.Queue()
        # touched in the loop's thread alone
        self._tasks: dict[K, asyncio.Task[None]] = {}
        self._thread: threading.Thread = threading.Thread(
            target=_serve, args=(self._loop,), daemon=True
        )
        self._thread.start()

    def start(self, key: K, events: AsyncIterator[Any]) -> None:
        """`events` relayed as they come, each with `key`."""
        _ = self._loop.call_soon_threadsafe(self._begin, key, events)

    def stop(self, key: K) -> None:
        """The stream of `key` stopped where it is: its events end with what came."""
        try:
            _ = self._loop.call_soon_threadsafe(self._cancel, key)
        except RuntimeError:
            pass  # the relay was closed, and every stream with it

    def next(self, timeout: float | None = None) -> tuple[K, Any] | None:
        """Any stream's next event, with its key; None where none came in time."""
        try:
            return self._handed.get(timeout=timeout)
        except queue.Empty:
            return None

    def taken(self, timeout: float | None = None) -> list[tuple[K, Any]]:
        """What came, waiting `timeout` seconds at most for the first of it."""
        first = self.next(timeout)
        taken = [] if first is None else [first]

        while first is not None:
            try:
                taken.append(self._handed.get_nowait())
            except queue.Empty:
                break

        return taken

    def close(self) -> None:
        """Every stream stopped, and ended, and the loop's thread let go."""
        if not self._thread.is_alive():
            return

        asyncio.run_coroutine_threadsafe(self._wound_down(), self._loop).result()
        _ = self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _begin(self, key: K, events: AsyncIterator[Any]) -> None:
        task = self._loop.create_task(_relayed(key, events, self._handed))
        self._tasks[key] = task
        task.add_done_callback(lambda _: self._ended(key))

    def _ended(self, key: K) -> None:
        del self._tasks[key]
        self._handed.put((key, ENDED))

    def _cancel(self, key: K) -> None:
        # a stream that ended before its stop came has nothing to stop
        if key in self._tasks:
            _ = self._tasks[key].cancel()

    async def _wound_down(self) -> None:
        tasks = list(self._tasks.values())

        for task in tasks:
            _ = task.cancel()

        _ = await asyncio.gather(*tasks, return_exceptions=True)


class Handed:
    """
    One stream relayed, its events as they come, and a TICK where nothing
    came for `tick` seconds, till it ends.
    """

    def __init__(self, events: AsyncIterator[Any], tick: float | None = None):
        self._tick: float | None = tick
        self._done: bool = False
        self._relay: Relay[int] = Relay()
        self._relay.start(0, events)

    def __iter__(self) -> Iterator[Any]:
        while not self._done:
            handed = self._relay.next(self._tick)

            if handed is None:
                yield TICK
                continue

            _, event = handed

            if event is ENDED:
                self._done = True
            elif isinstance(event, BaseException):
                raise event
            else:
                yield event

    def stop(self) -> None:
        """Stop the stream where it is: its events end with what came."""
        self._relay.stop(0)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        # a caller that goes away before the stream ends takes it along
        self._relay.close()


def _serve(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)

    try:
        loop.run_forever()
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


async def _relayed(
    key: Any, events: AsyncIterator[Any], handed: queue.Queue[Any]
) -> None:
    try:
        async for event in events:
            handed.put((key, event))
    except asyncio.CancelledError:
        pass  # stopped: its events end with what came
    except Exception as e:  # noqa: BLE001
        handed.put((key, e))

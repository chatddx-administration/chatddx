# pyright: basic
"""
Running the cell on a case, or on each case with a tag, one after another,
and recording each run as one of its trial's.

Ctrl-C stops a run as it streams: asyncio cancels it, pydantic-ai closes its
stream and the connection it came over, which is all the server hears of it,
and the run is recorded as stopped, with what had come. A run already done is
written down, and scored, whole: Ctrl-C waits for that, unless it comes again.
"""

import asyncio
import signal
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from types import FrameType
from typing import Any, Self

from django.utils import timezone
from pydantic_ai import UnexpectedModelBehavior, UsageLimitExceeded
from rich.text import Text

from chatddx.history.models import RunModel, RunStatus, ScoreModel
from chatddx.history.record import Branches, Outcome, record
from chatddx.repl.cell import NONE
from chatddx.repl.render import (
    LABEL,
    LATER,
    Columns,
    Streamed,
    Tally,
    show_events,
    show_scores,
    show_validity,
    show_views,
    tally_events,
)
from chatddx.repl.scoring import summary
from chatddx.repl.shell import SHARED_BY, Repl, drawn_seed
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailIn
from chatddx.repo.entities.tool.pydantic import ToolBranchOut
from chatddx.repo.families.django import BranchModel
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.runtime.resolution import CellRefused, Resolution
from chatddx.runtime.run import TOOL_ROUNDS, Run, cause_of, invalid
from chatddx.scoring.score import Scoring

STOPPED = Outcome(RunStatus.ERRORED, error="stopped")

# the largest seed a trial keeps, and vLLM takes
MAX_SEED = 2**63 - 1


@dataclass(frozen=True)
class Ready:
    """What the cell runs with: how it resolved, its credential, and its tools."""

    resolution: Resolution
    api_key: str | None
    tools: dict[str, ToolBranchOut]


def seed(repl: Repl, word: str | None = None) -> None:
    """
    Draw a fresh seed for `run` and `batch` to send; or hold SEED, or none,
    to run unseeded.
    """
    if word is None:
        repl.seed = drawn_seed()
    elif word == NONE:
        repl.seed = None
    else:
        chosen = _seed_of(repl, word)

        if chosen is None:
            return

        repl.seed = chosen

    held = f"#{repl.seed}" if repl.seed is not None else "none: runs go unseeded"
    repl.console.print(f"seed: {held}")


def run(repl: Repl, name: str, seed: str | None = None) -> None:
    """
    Run the cell on a case, with SEED or else the seed the repl holds, stream
    the run, record it as a run of the trial the cell, the case and the seed
    make, and hold it to the scorers that apply. An answer that doesn't
    come, or doesn't parse, doesn't hold, where one is asked for; an LLM or
    server that fails mid-run is said, and recorded.
    """
    chosen = repl.seed if seed is None else _seed_of(repl, seed)

    if seed is not None and chosen is None:
        return

    ready = _ready(repl)

    if ready is None or not _seedable(repl, ready, chosen):
        return

    case = get_visible_branch_model("case", repl.identity, name)
    run = _made(repl, ready, case, chosen)

    if run is None:
        return

    repl.console.print(f"trial: {_described(repl, case, run)}", style="bold")

    started = timezone.now()

    try:
        streamed = asyncio.run(_stream(repl, run))
    except KeyboardInterrupt:
        repl.console.print("\n(stopped)", style=LABEL)
        outcome = STOPPED
    except Exception as e:  # noqa: BLE001
        outcome = _failed(e, ready.resolution)
        unparsed = isinstance(e, UnexpectedModelBehavior)
        repl.error(f"invalid: {outcome.error}" if unparsed else f"\n{outcome.error}")
    else:
        valid = _judge(repl, ready.resolution, streamed)
        outcome = Outcome(RunStatus.COMPLETED, answer=streamed.answer, valid=valid)

    finished = timezone.now()

    with _held():
        recorded = _recorded(repl, ready, case, run, outcome, started, finished)

        if recorded is None:
            return

        show_scores(repl.console, _scored(repl, recorded))
        repl.console.print(
            f"recorded as run {recorded.trial.runs.count()} of trial "
            + str(recorded.trial.uuid)[:8],
            style=LABEL,
        )


def batch(repl: Repl, *tags: str) -> None:
    """
    Run the cell on each case tagged with any of `tags`, one after another,
    each on a line of its own: the case, its output tokens as they stream,
    then what came of its run and what each scorer made of it. Each run is
    recorded and scored as `run` records and scores it, and the batch ends
    with each scorer's metrics.

    The first Ctrl-C lets the run under way finish, and stops the batch
    after it; the second stops that run too, recorded as stopped; a third
    is let through, for one that hangs.
    """
    ready = _ready(repl)

    if ready is None or not _seedable(repl, ready, repl.seed):
        return

    tagged = " or ".join(tags)
    distinct: dict[int, BranchModel] = {}

    # two names for one vignette are one case, and it runs once
    for case in repl.tagged("case", tags):
        _ = distinct.setdefault(case.trail_id, case)

    cases = list(distinct.values())

    if not cases:
        repl.error(f"no case tagged {tagged} for {repl.identity}")
        return

    cell = repl.cell
    assert cell.stack
    scoring = Scoring(repl.identity)
    views = ready.resolution.output.views
    columns = Columns(
        (case.name for case in cases),
        (scorer.name for scorer in scoring.scorers if scorer.view in views),
    )
    many = "s" if len(cases) > 1 else ""

    repl.console.print(
        f"batch: {cell.label} × {cell.stack.name} × {len(cases)} case{many}"
        + f" tagged {tagged}, "
        + (f"seed {repl.seed}" if repl.seed is not None else "unseeded"),
        style="bold",
    )
    repl.console.print(columns.header())

    made: list[ScoreModel] = []
    ran = 0

    with _Stopping() as stopping:
        try:
            for case in cases:
                if stopping.asked:
                    break

                run = _made(repl, ready, case, repl.seed)

                if run is None:
                    break

                with Tally(repl.console, columns, case.name) as tally:
                    stopping.tally = tally
                    started = timezone.now()

                    try:
                        streamed = asyncio.run(_tally(run, tally, stopping))
                    except asyncio.CancelledError:
                        outcome = STOPPED
                    except Exception as e:  # noqa: BLE001
                        outcome = _failed(e, ready.resolution)
                    else:
                        outcome = Outcome(
                            RunStatus.COMPLETED,
                            answer=streamed.answer,
                            valid=_holds(ready.resolution, streamed.answer),
                        )

                    finished = timezone.now()
                    recorded = _recorded(
                        repl, ready, case, run, outcome, started, finished
                    )
                    scores = (
                        [] if recorded is None else _scored(repl, recorded, scoring)
                    )
                    tally.end(outcome, scores)
                    stopping.tally = None

                made += scores
                ran += 1
        except KeyboardInterrupt:
            # the third Ctrl-C, or one outside what the batch holds
            pass

    if made:
        summary(repl, scoring, made)

    if ran < len(cases):
        repl.console.print(f"stopped after {ran} of {len(cases)} cases", style=LABEL)


def _ready(repl: Repl) -> Ready | None:
    """What the cell runs with, or None, having said why it can't run."""
    cell = repl.cell

    if not (cell.configuration and cell.stack):
        repl.error(
            "the cell needs a configuration and a stack: cell CONFIGURATION STACK"
        )
        return None

    owner = cell.configuration.owner.name

    if owner not in (repl.identity, SHARED_BY["configuration"]):
        repl.error(f"{cell.name} is {owner}'s: save it as your own first: save NAME")
        return None

    try:
        resolution = repl.resolve()
    except CellRefused as e:
        repl.say_refusals(e.refusals)
        return None

    api_key = repl.secret(resolution.credential)

    if resolution.credential and api_key is None:
        repl.error(f"{repl.identity} has no secret '{resolution.credential}'")
        return None

    return Ready(resolution, api_key, repl.tools())


def _seed_of(repl: Repl, word: str) -> int | None:
    """The seed `word` names, or None, having said why it names none."""
    if not word.isdigit() or int(word) > MAX_SEED:
        repl.error(f"a seed is a whole number up to {MAX_SEED}, not '{word}'")
        return None

    return int(word)


def _seedable(repl: Repl, ready: Ready, seed: int | None) -> bool:
    """
    Whether the cell can run with `seed`: greedy sampling ignores a seed, so
    a seeded run of it would claim a reproducibility the seed plays no part
    in, and a second seed would repeat it rather than replicate it.
    """
    if seed is None or not _greedy(ready.resolution):
        return True

    repl.error(
        "refused: seed: sampling is greedy (temperature 0), which ignores the"
        + " seed: `seed none` runs it unseeded"
    )
    return False


def _greedy(resolution: Resolution) -> bool:
    writes = resolution.sampling.writes
    return writes.get("temperature") == 0 or writes.get("top_k") == 1


def _made(repl: Repl, ready: Ready, case: BranchModel, seed: int | None) -> Run | None:
    """A run of the cell on `case`, or None, having said why a tool can't run."""
    try:
        return Run(
            ready.resolution,
            case.trail.vignette,
            api_key=ready.api_key,
            transport=repl.transport,
            seed=seed,
            implementations={
                tool: branch.details.implementation.function
                for tool, branch in ready.tools.items()
                if branch.details.implementation is not None
            },
        )
    except ValueError as e:
        repl.error(str(e))
        return None


def _described(repl: Repl, case: BranchModel, run: Run) -> str:
    """What a run is described as: its trial's cell, case and seed."""
    cell = repl.cell
    assert cell.stack
    seeded = f" (seed {run.seed})" if run.seed is not None else ""

    return f"{cell.label} × {cell.stack.name} × {case.name}{seeded}"


async def _stream(repl: Repl, run: Run) -> Streamed:
    async with run.stream() as events:
        return await show_events(repl.console, events)


async def _tally(run: Run, tally: Tally, stopping: "_Stopping") -> Streamed:
    stopping.streaming = (asyncio.get_running_loop(), asyncio.current_task())

    try:
        async with run.stream() as events:
            return await tally_events(events, tally)
    finally:
        stopping.streaming = None


def _failed(error: Exception, resolution: Resolution) -> Outcome:
    """
    What came of a run that ended in `error`: an answer that doesn't parse,
    or an LLM that doesn't stop calling tools, doesn't hold, where one is
    asked for; anything else is the LLM's, or its server's, failure.
    """
    unheld = False if resolution.coercion is not None else None

    match error:
        case UnexpectedModelBehavior():
            unparsed = f"the answer doesn't parse: {cause_of(error)}"
            return Outcome(RunStatus.COMPLETED, valid=unheld, error=unparsed)
        case UsageLimitExceeded():
            stopped = f"stopped: still calling tools after {TOOL_ROUNDS} rounds"
            return Outcome(RunStatus.COMPLETED, valid=unheld, error=stopped)
        case _:
            return Outcome(RunStatus.ERRORED, error=f"{type(error).__name__}: {error}")


def _holds(resolution: Resolution, answer: Any) -> bool | None:
    """Whether the answer holds to its schema, where there is one to hold to."""
    if resolution.coercion is None:
        return None

    return invalid(resolution.coercion.schema, answer) is None


def _judge(repl: Repl, resolution: Resolution, streamed: Streamed) -> bool | None:
    """
    Whether the LLM reasoned as it was asked to, whether its answer holds
    to its schema, and what the output's views read from it: the facts are
    claims, and a run is what shows whether the LLM honours them
    (datamodel.md §2). Answer with whether it holds, where there is a
    schema to hold to.
    """
    intent = resolution.reasoning.intent

    if intent != "off" and not streamed.thought:
        repl.console.print(
            Text(
                f"no thinking came back, though reasoning resolved to '{intent}'",
                style=LATER,
            )
        )
    elif intent == "off" and streamed.thought:
        repl.console.print(
            Text(
                "thinking came back, though reasoning resolved to 'off'",
                style=LATER,
            )
        )

    answer = streamed.answer
    valid: bool | None = None

    if resolution.coercion is not None:
        problem = invalid(resolution.coercion.schema, answer)
        valid = problem is None
        show_validity(repl.console, problem)

    show_views(repl.console, resolution.output, answer)

    return valid


def _recorded(
    repl: Repl,
    ready: Ready,
    case: BranchModel,
    run: Run,
    outcome: Outcome,
    started: datetime,
    finished: datetime,
) -> RunModel | None:
    """The run, recorded as a run of its trial, or None, having said why not."""
    cell = repl.cell
    assert cell.stack

    try:
        return record(
            repl.identity,
            ConfigurationTrailIn.model_validate(cell.slices, from_attributes=True),
            Branches(
                stack=cell.stack.id,
                llm=repl.llm_of(cell.stack)[1],
                tools={
                    ready.tools[tool].id: ran.blob
                    for tool, ran in run.implementations.items()
                },
            ),
            case.trail_id,
            run,
            outcome,
            started,
            finished,
            description=_described(repl, case, run),
        )
    except Exception as e:  # noqa: BLE001
        repl.error(f"not recorded: {type(e).__name__}: {e}")
        return None


def _scored(
    repl: Repl, recorded: RunModel, scoring: Scoring | None = None
) -> list[ScoreModel]:
    """What each scorer that applies made of a run, or nothing, having said why."""
    try:
        return (scoring or Scoring(repl.identity)).score(recorded)
    except Exception as e:  # noqa: BLE001
        repl.error(f"not scored: {type(e).__name__}: {e}")
        return []


@contextmanager
def _held() -> Generator[Callable[[], bool]]:
    """
    Hold Ctrl-C off until the block is done, and answer whether it came; the
    second is let through, for a block that hangs.
    """
    pressed = 0

    def hold(_signal: int, _frame: FrameType | None) -> None:
        nonlocal pressed
        pressed += 1

        if pressed > 1:
            raise KeyboardInterrupt

    held = signal.signal(signal.SIGINT, hold)

    try:
        yield lambda: pressed > 0
    finally:
        signal.signal(signal.SIGINT, held)


class _Stopping:
    """
    Ctrl-C through a batch. The first asks it to stop after the run under
    way, which the line says; the second cancels that run's stream, as
    asyncio would on its own; the third is let through. Held here, none
    reaches asyncio, which only takes Ctrl-C from Python's own handler.
    """

    def __init__(self):
        self.pressed: int = 0
        self.tally: Tally | None = None
        self.streaming: tuple[asyncio.AbstractEventLoop, Any] | None = None
        self._held: Any = None

    @property
    def asked(self) -> bool:
        return self.pressed > 0

    def __enter__(self) -> Self:
        self._held = signal.signal(signal.SIGINT, self._pressed)
        return self

    def __exit__(self, *_: object) -> None:
        signal.signal(signal.SIGINT, self._held)

    def _pressed(self, _signal: int, _frame: FrameType | None) -> None:
        self.pressed += 1

        if self.pressed == 1:
            if self.tally is not None:
                self.tally.stopping()
        elif self.pressed == 2 and self.streaming is not None:
            loop, task = self.streaming
            loop.call_soon_threadsafe(task.cancel)
        else:
            raise KeyboardInterrupt

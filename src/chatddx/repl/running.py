import asyncio
import signal
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import datetime
from types import FrameType
from typing import Any, Self

from django.utils import timezone
from pydantic_ai import UnexpectedModelBehavior
from rich.text import Text

from chatddx.history.models import RunModel, RunStatus, ScoreModel
from chatddx.history.record import Outcome
from chatddx.repl.bench import (
    MAX_SEED,
    SHARED_BY,
    STOPPED,
    Ready,
    drawn_seed,
    failed,
    greedy,
    holds,
    unheeded,
)
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
from chatddx.repl.shell import Repl
from chatddx.repo.families.django import BranchModel
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.runtime.resolution import CellRefused, Resolution
from chatddx.runtime.run import Run, Runaway, invalid
from chatddx.scoring.score import Scoring


def seed(repl: Repl, word: str | None = None) -> None:
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

    repl.console.print(f"trial: {repl.described(case.name, run.seed)}", style="bold")

    started = timezone.now()

    try:
        streamed = asyncio.run(_stream(repl, run))
    except KeyboardInterrupt:
        repl.console.print("\n(stopped)", style=LABEL)
        outcome = STOPPED
    except Runaway as e:
        outcome = failed(e, run)
        repl.error(f"\n{outcome.error}")
        _ = _shown(repl, ready.resolution, outcome.answer)
    except Exception as e:  # noqa: BLE001
        outcome = failed(e, run)
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
    ready = _ready(repl)

    if ready is None or not _seedable(repl, ready, repl.seed):
        return

    tagged = " or ".join(tags)
    cases = repl.cases(tags)

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
                        outcome = failed(e, run)
                    else:
                        outcome = Outcome(
                            RunStatus.COMPLETED,
                            answer=streamed.answer,
                            valid=holds(ready.resolution, streamed.answer),
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
            pass

    if made:
        summary(repl, scoring, made)

    if ran < len(cases):
        repl.console.print(f"stopped after {ran} of {len(cases)} cases", style=LABEL)


def _ready(repl: Repl) -> Ready | None:
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
    if not word.isdigit() or int(word) > MAX_SEED:
        repl.error(f"a seed is a whole number up to {MAX_SEED}, not '{word}'")
        return None

    return int(word)


def _seedable(repl: Repl, ready: Ready, seed: int | None) -> bool:
    if seed is None or not greedy(ready.resolution.sampling):
        return True

    repl.error(
        "refused: seed: sampling is greedy (temperature 0), which ignores the"
        + " seed: `seed none` runs it unseeded"
    )
    return False


def _made(repl: Repl, ready: Ready, case: BranchModel, seed: int | None) -> Run | None:
    try:
        return repl.made(ready, case.trail.vignette, seed)
    except ValueError as e:
        repl.error(str(e))
        return None


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


def _judge(repl: Repl, resolution: Resolution, streamed: Streamed) -> bool | None:
    warning = unheeded(resolution.reasoning.intent, streamed.thought)

    if warning is not None:
        repl.console.print(Text(warning, style=LATER))

    return _shown(repl, resolution, streamed.answer)


def _shown(repl: Repl, resolution: Resolution, answer: Any) -> bool | None:
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
    try:
        return repl.recorded(
            ready,
            case.trail_id,
            run,
            outcome,
            started,
            finished,
            repl.described(case.name, run.seed),
        )
    except Exception as e:  # noqa: BLE001
        repl.error(f"not recorded: {type(e).__name__}: {e}")
        return None


def _scored(
    repl: Repl, recorded: RunModel, scoring: Scoring | None = None
) -> list[ScoreModel]:
    try:
        return (scoring or Scoring(repl.identity)).score(recorded)
    except Exception as e:  # noqa: BLE001
        repl.error(f"not scored: {type(e).__name__}: {e}")
        return []


@contextmanager
def _held() -> Generator[Callable[[], bool]]:
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

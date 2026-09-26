import asyncio
import signal
from collections.abc import Callable, Generator
from contextlib import contextmanager
from types import FrameType
from typing import Any, Self

from pydantic_ai import UnexpectedModelBehavior
from rich.text import Text

from chatddx.bench.bench import (
    MAX_SEED,
    Incomplete,
    NotOwn,
    NotReady,
    Ready,
    Trial,
    drawn_seed,
)
from chatddx.bench.cell import NONE
from chatddx.bench.outcome import unheeded
from chatddx.bench.plan import Plan, Planned
from chatddx.bench.sending import Sending, Written
from chatddx.history.models import ConversationContext, ScoreModel
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
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.runtime.resolution import CellRefused, Resolution
from chatddx.runtime.run import Runaway, invalid
from chatddx.scoring.score import Scoring

# the command that clears what stands in a cell's way
HINTS: dict[type[NotReady], str] = {
    Incomplete: "cell CONFIGURATION STACK",
    NotOwn: "save NAME",
}


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
    trial = Trial.on(ready, case, chosen)
    sending = _sending(repl, trial)

    if sending is None:
        return

    repl.console.print(f"trial: {trial.description}", style="bold")

    try:
        streamed = asyncio.run(_stream(repl, sending))
    except KeyboardInterrupt:
        repl.console.print("\n(stopped)", style=LABEL)
        sending.stop()
    else:
        _said(repl, sending, streamed)

    with _held():
        written = _written(repl, sending)

        if written.run is None:
            return

        show_scores(repl.console, written.scores)
        repl.console.print(
            f"recorded as run {written.run.trial.runs.count()} of trial "
            + str(written.run.trial.uuid)[:8],
            style=LABEL,
        )


def batch(repl: Repl, *tags: str) -> None:
    ready = _ready(repl)

    if ready is None or not _seedable(repl, ready, repl.seed):
        return

    plan = Plan([Planned(ready.cell, ready)], repl.cases(tags), tags, repl.seed)

    if not plan.cases:
        repl.error(f"no case tagged {plan.tagged} for {repl.identity}")
        return

    scoring = Scoring(repl.identity)
    views = ready.resolution.output.views
    columns = Columns(
        (case.name for case in plan.cases),
        (scorer.name for scorer in scoring.scorers if scorer.view in views),
    )

    repl.console.print(
        f"batch: {plan.description}, "
        + (f"seed {repl.seed}" if repl.seed is not None else "unseeded"),
        style="bold",
    )
    repl.console.print(columns.header())

    trials = plan.trials
    made: list[ScoreModel] = []
    ran = 0

    with _Stopping() as stopping:
        try:
            for trial in trials:
                if stopping.asked:
                    break

                sending = _sending(repl, trial, scoring)

                if sending is None:
                    break

                with Tally(repl.console, columns, trial.called) as tally:
                    stopping.tally = tally

                    try:
                        _ = asyncio.run(_tally(sending, tally, stopping))
                    except asyncio.CancelledError:
                        sending.stop()

                    written = _written(repl, sending)
                    assert sending.outcome is not None
                    tally.end(sending.outcome, written.scores)
                    stopping.tally = None

                made += written.scores
                ran += 1
        except KeyboardInterrupt:
            pass

    if made:
        summary(repl, scoring, made)

    if ran < len(trials):
        repl.console.print(f"stopped after {ran} of {len(trials)} cases", style=LABEL)


def _ready(repl: Repl) -> Ready | None:
    try:
        return repl.ready(repl.cell)
    except CellRefused as e:
        repl.say_refusals(e.refusals)
    except NotReady as e:
        hint = HINTS.get(type(e))
        repl.error(f"{e}: {hint}" if hint else str(e))

    return None


def _seed_of(repl: Repl, word: str) -> int | None:
    if not word.isdigit() or int(word) > MAX_SEED:
        repl.error(f"a seed is a whole number up to {MAX_SEED}, not '{word}'")
        return None

    return int(word)


def _seedable(repl: Repl, ready: Ready, seed: int | None) -> bool:
    if seed is None or not ready.greedy:
        return True

    repl.error(
        "refused: seed: sampling is greedy (temperature 0), which ignores the"
        + " seed: `seed none` runs it unseeded"
    )
    return False


def _sending(
    repl: Repl, trial: Trial, scoring: Scoring | None = None
) -> Sending | None:
    try:
        return Sending(repl, trial, ConversationContext.REPL, scoring)
    except ValueError as e:
        repl.error(str(e))
        return None


async def _stream(repl: Repl, sending: Sending) -> Streamed:
    return await show_events(repl.console, sending.events())


async def _tally(sending: Sending, tally: Tally, stopping: "_Stopping") -> Streamed:
    stopping.streaming = (asyncio.get_running_loop(), asyncio.current_task())

    try:
        return await tally_events(sending.events(), tally)
    finally:
        stopping.streaming = None


def _said(repl: Repl, sending: Sending, streamed: Streamed) -> None:
    """What the run came to, where it didn't come to an answer as asked."""
    outcome = sending.outcome
    resolution = sending.trial.ready.resolution
    assert outcome is not None

    match sending.error:
        case None:
            _ = _judge(repl, resolution, streamed)
        case Runaway():
            repl.error(f"\n{outcome.error}")
            _ = _shown(repl, resolution, outcome.answer)
        case UnexpectedModelBehavior():
            repl.error(f"invalid: {outcome.error}")
        case _:
            repl.error(f"\n{outcome.error}")


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


def _written(repl: Repl, sending: Sending) -> Written:
    written = sending.written()

    for unwritten in (written.unrecorded, written.unscored):
        if unwritten is not None:
            repl.error(unwritten)

    return written


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

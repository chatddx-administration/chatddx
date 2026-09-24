# pyright: basic
"""Running a case on the cell, as a trial, and recording the run."""

import asyncio

from django.utils import timezone
from pydantic_ai import UnexpectedModelBehavior, UsageLimitExceeded
from rich.text import Text

from chatddx.core.repl.render import (
    LABEL,
    LATER,
    Streamed,
    show_events,
    show_scores,
    show_validity,
    show_views,
)
from chatddx.core.repl.shell import SHARED_BY, Repl
from chatddx.history.models import RunStatus
from chatddx.history.record import Branches, Outcome, record
from chatddx.repo.entities.configuration.pydantic import ConfigurationTrailIn
from chatddx.repo.store.branch import get_visible_branch_model
from chatddx.runtime.resolution import CellRefused, Resolution
from chatddx.runtime.trial import TOOL_ROUNDS, Trial, cause_of, invalid
from chatddx.scoring.score import Scoring


def run(repl: Repl, name: str, seed: str | None = None) -> None:
    """
    Make a trial of the cell on a case, stream it, record the run, and hold
    it to the scorers that apply. An answer that doesn't come, or doesn't
    parse, doesn't hold, where one is asked for; an LLM or server that
    fails mid-run is said, and recorded.
    """
    cell = repl.cell

    if seed is not None and not seed.isdigit():
        repl.error(f"a seed is a whole number, not '{seed}'")
        return

    if not (cell.configuration and cell.stack):
        repl.error(
            "the cell needs a configuration and a stack: cell CONFIGURATION STACK"
        )
        return

    owner = cell.configuration.owner.name

    if owner not in (repl.identity, SHARED_BY["configuration"]):
        repl.error(f"{cell.name} is {owner}'s: save it as your own first: save NAME")
        return

    try:
        resolution = repl.resolve()
    except CellRefused as e:
        repl.say_refusals(e.refusals)
        return

    case = get_visible_branch_model("case", repl.identity, name)
    api_key = repl.secret(resolution.credential)

    if resolution.credential and api_key is None:
        repl.error(f"{repl.identity} has no secret '{resolution.credential}'")
        return

    tools = repl.tools()

    try:
        trial = Trial(
            resolution,
            case.trail.vignette,
            api_key=api_key,
            transport=repl.transport,
            seed=int(seed) if seed is not None else None,
            implementations={
                tool: branch.details.implementation.function
                for tool, branch in tools.items()
                if branch.details.implementation is not None
            },
        )
    except ValueError as e:
        repl.error(str(e))
        return

    seeded = f" (seed {seed})" if seed is not None else ""
    header = f"{cell.label} × {cell.stack.name} × {case.name}{seeded}"
    repl.console.print(f"trial: {header}", style="bold")

    unheld = False if resolution.coercion is not None else None
    started = timezone.now()

    try:
        streamed = asyncio.run(_stream(repl, trial))
    except KeyboardInterrupt:
        repl.console.print("\n(stopped)", style=LABEL)
        outcome = Outcome(RunStatus.ERRORED, error="stopped")
    except UnexpectedModelBehavior as e:
        unparsed = f"the answer doesn't parse: {cause_of(e)}"
        repl.error(f"invalid: {unparsed}")
        outcome = Outcome(RunStatus.COMPLETED, valid=unheld, error=unparsed)
    except UsageLimitExceeded:
        stopped = f"stopped: still calling tools after {TOOL_ROUNDS} rounds"
        repl.error(f"\n{stopped}")
        outcome = Outcome(RunStatus.COMPLETED, valid=unheld, error=stopped)
    except Exception as e:  # noqa: BLE001
        repl.error(f"\n{type(e).__name__}: {e}")
        outcome = Outcome(RunStatus.ERRORED, error=f"{type(e).__name__}: {e}")
    else:
        valid = _judge(repl, resolution, streamed)
        outcome = Outcome(RunStatus.COMPLETED, output=streamed.answer, valid=valid)

    finished = timezone.now()

    try:
        recorded = record(
            repl.identity,
            ConfigurationTrailIn.model_validate(cell.slices, from_attributes=True),
            Branches(
                stack=cell.stack.id,
                llm=repl.llm_of(cell.stack)[1],
                tools={
                    tools[tool].id: ran.blob
                    for tool, ran in trial.implementations.items()
                },
            ),
            case.trail_id,
            trial,
            outcome,
            started,
            finished,
            description=header,
        )
    except Exception as e:  # noqa: BLE001
        repl.error(f"not recorded: {type(e).__name__}: {e}")
        return

    try:
        show_scores(repl.console, Scoring(repl.identity).score(recorded))
    except Exception as e:  # noqa: BLE001
        repl.error(f"not scored: {type(e).__name__}: {e}")

    repl.console.print(
        f"recorded as run {recorded.trial.runs.count()} of trial "
        + str(recorded.trial.uuid)[:8],
        style=LABEL,
    )


async def _stream(repl: Repl, trial: Trial) -> Streamed:
    async with trial.stream() as events:
        return await show_events(repl.console, events)


def _judge(repl: Repl, resolution: Resolution, streamed: Streamed) -> bool | None:
    """
    Whether the LLM reasoned as it was asked to, whether its answer holds
    to its schema, and what the output's views read from it: the facts are
    claims, and a trial is what shows whether the LLM honours them
    (new-datamodel.md §2). Answer with whether it holds, where there is a
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

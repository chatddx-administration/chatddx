"""How a run came out: what the repl, the API and the portal record of it."""

from typing import Any

from pydantic_ai import UnexpectedModelBehavior, UsageLimitExceeded

from chatddx.history.models import RunStatus
from chatddx.history.record import Outcome
from chatddx.repo.entities.reasoning.pydantic import Intent
from chatddx.runtime.resolution import Resolution
from chatddx.runtime.run import TOOL_ROUNDS, Run, Runaway, cause_of, invalid

STOPPED = Outcome(RunStatus.ERRORED, error="stopped")


def failed(error: Exception, run: Run) -> Outcome:
    resolution = run.resolution
    unheld = False if resolution.coercion is not None else None

    match error:
        case UnexpectedModelBehavior():
            unparsed = f"the answer doesn't parse: {cause_of(error)}"
            return Outcome(RunStatus.COMPLETED, valid=unheld, error=unparsed)
        case UsageLimitExceeded():
            stopped = f"stopped: still calling tools after {TOOL_ROUNDS} rounds"
            return Outcome(RunStatus.COMPLETED, valid=unheld, error=stopped)
        case Runaway():
            # what came before stands as the answer, and the run is flagged
            answer = run.salvaged()
            return Outcome(
                RunStatus.COMPLETED,
                answer=answer,
                valid=holds(resolution, answer),
                error=f"stopped: {error}",
            )
        case _:
            return Outcome(RunStatus.ERRORED, error=f"{type(error).__name__}: {error}")


def holds(resolution: Resolution, answer: Any) -> bool | None:
    if resolution.coercion is None:
        return None

    return invalid(resolution.coercion.schema, answer) is None


def unheeded(intent: Intent, thought: bool) -> str | None:
    if intent != "off" and not thought:
        return f"no thinking came back, though reasoning resolved to '{intent}'"

    if intent == "off" and thought:
        return "thinking came back, though reasoning resolved to 'off'"

    return None

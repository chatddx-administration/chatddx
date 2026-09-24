# pyright: basic
"""The identity's runs, and each again as it streamed."""

from datetime import datetime
from typing import Any, cast

from django.utils import timezone
from pydantic_ai import ModelMessagesTypeAdapter
from rich.table import Table
from rich.text import Text

from chatddx.core.repl.render import (
    LABEL,
    REFUSED,
    VALID,
    show_messages,
    show_validity,
    show_views,
)
from chatddx.core.repl.shell import Repl
from chatddx.history.models import MessageKind, RunModel, RunStatus
from chatddx.repo.entities.output.pydantic import OutputTrailSpec
from chatddx.repo.shufflers.trail import load_trail
from chatddx.runtime.trial import invalid


def runs(repl: Repl, count: str = "20") -> None:
    if not count.isdigit():
        repl.error(f"a count is a whole number, not '{count}'")
        return

    latest = list(
        RunModel.objects.filter(owner__name=repl.identity)
        .select_related("trial", "session")
        .order_by("-timestamp", "-pk")[: int(count)]
    )

    if not latest:
        repl.console.print(f"{repl.identity} has no runs", style=LABEL)
        return

    table = Table(box=None, header_style="bold")

    for column in ("run", "when", "trial", "what ran", "outcome"):
        table.add_column(column)

    for run in latest:
        table.add_row(
            _short(run.uuid),
            _when(run.timestamp),
            _short(run.trial.uuid),
            run.session.description if run.session else "—",
            _outcome(run),
        )

    repl.console.print(table)


def replay(repl: Repl, prefix: str | None = None) -> None:
    found = RunModel.objects.filter(owner__name=repl.identity).select_related(
        "trial__configuration__output", "session", "client"
    )

    if prefix is not None:
        found = found.filter(uuid__startswith=prefix)

    candidates = list(found.order_by("-timestamp", "-pk")[:2])

    if not candidates:
        which = f"no run '{prefix}'" if prefix else "no runs"
        repl.error(f"{repl.identity} has {which}")
        return

    if prefix is not None and len(candidates) > 1:
        repl.error(f"more than one run starts with '{prefix}'")
        return

    run = candidates[0]
    what = run.session.description if run.session else "—"
    repl.console.print(
        f"run {_short(run.uuid)} of trial {_short(run.trial.uuid)}: {what}",
        style="bold",
    )
    repl.console.print(
        f"{_when(run.timestamp)}, {run.status}, {_client(run)}", style=LABEL
    )

    stored = list(run.session.messages.all()) if run.session else []
    messages = ModelMessagesTypeAdapter.validate_python(
        [message.payload for message in stored if message.kind != MessageKind.ERROR]
    )
    answered = run.output is not None
    show_messages(repl.console, messages, answered)

    for message in stored:
        if message.kind == MessageKind.ERROR:
            repl.error(str(message.payload["error"]))

    if answered:
        output = cast(
            OutputTrailSpec,
            load_trail(
                "output",
                run.trial.configuration.output.fingerprint,
                OutputTrailSpec,
            ),
        )

        if run.valid is not None and output.schema is not None:
            show_validity(repl.console, invalid(output.schema, run.output))

        show_views(repl.console, output, run.output)


def _short(value: Any) -> str:
    """An id as the repl shows it: the first digits of a uuid."""
    return str(value)[:8]


def _when(moment: datetime) -> str:
    return timezone.localtime(moment).strftime("%Y-%m-%d %H:%M")


def _client(run: RunModel) -> str:
    """The client a run ran on: its build, or the revision of a dev shell."""
    if run.client is None:
        return "on no client it recorded"

    if run.client.build is not None:
        return f"on {run.client.build}"

    rev = run.client_rev or ""
    dirty = "-dirty" if rev.endswith("-dirty") else ""

    return f"from a dev shell at {rev[:12]}{dirty}" if rev else "from a dev shell"


def _outcome(run: RunModel) -> Text:
    """
    What came of a run, as the list of runs says it: an error where it came
    to no answer that holds.
    """
    if run.status == RunStatus.ERRORED:
        return Text(f"errored: {_clipped_line(run.error or '')}", style=REFUSED)

    if run.error is not None:
        return Text(_clipped_line(run.error), style=REFUSED)

    match run.valid:
        case True:
            return Text("valid", style=VALID)
        case False:
            return Text("invalid", style=REFUSED)
        case None:
            return Text(run.status)


def _clipped_line(text: str, width: int = 60) -> str:
    line = text.splitlines()[0] if text else ""
    return line if len(line) <= width else line[: width - 1] + "…"

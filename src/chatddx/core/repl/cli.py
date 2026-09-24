# pyright: basic
"""
`chatddx repl IDENTITY`: lines read as they are typed, or piped in, each
echoed after the prompt as if it was typed. A name holds `-`, `@` and `.`,
so only a space ends the word completed. httpx's line per request is kept
out of the answer as it streams.
"""

import logging
import readline
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from chatddx.core.models import IdentityModel
from chatddx.core.repl.commands import complete, handle
from chatddx.core.repl.shell import Repl

HISTORY = Path.home() / ".chatddx_history"


def repl(
    identity_name: Annotated[str, typer.Argument()],
    history: Annotated[
        Path,
        typer.Option(help="where the lines you type are kept"),
    ] = HISTORY,
):
    """Run cases on a configuration and a stack."""
    if not IdentityModel.objects.filter(name=identity_name).exists():
        typer.echo(
            f"no identity '{identity_name}': chatddx init-data {identity_name}",
            err=True,
        )
        raise typer.Exit(1)

    for logger in ("httpx", "httpx2"):
        logging.getLogger(logger).setLevel(logging.WARNING)

    shell = Repl(identity_name, Console())

    matches: list[str] = []

    def completer(_word: str, state: int) -> str | None:
        nonlocal matches

        if state == 0:
            line = readline.get_line_buffer()[: readline.get_endidx()]
            matches = complete(shell.completions(), line)

        return f"{matches[state]} " if state < len(matches) else None

    readline.set_completer(completer)
    readline.set_completer_delims(" ")
    readline.parse_and_bind("tab: complete")

    try:
        readline.read_history_file(history)
    except OSError:
        pass

    interactive = sys.stdin.isatty()

    try:
        while True:
            try:
                line = input(shell.prompt)
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                print()
                break

            if not interactive:
                print(line)

            if not handle(shell, line):
                break
    finally:
        try:
            readline.write_history_file(history)
        except OSError:
            pass

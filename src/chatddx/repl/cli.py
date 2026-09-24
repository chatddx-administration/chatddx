# pyright: basic
"""
`chatddx repl IDENTITY`: lines read as they are typed, or piped in, each
echoed after the prompt as if it was typed. A name holds `-`, `@` and `.`,
so only a space ends the word completed. httpx's line per request is kept
out of the answer as it streams.

The database connection is let go after each line, as Django lets it go
after each request: an idle repl holds none, and the next line opens one,
whether or not the server dropped the last.
"""

import logging
import readline
import sys
from pathlib import Path
from typing import Annotated

import typer
from django.db import connections
from rich.console import Console

from chatddx.core.models import IdentityModel
from chatddx.repl.commands import complete, handle
from chatddx.repl.shell import Repl

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
    let_go()

    matches: list[str] = []

    def completer(_word: str, state: int) -> str | None:
        nonlocal matches

        if state == 0:
            line = readline.get_line_buffer()[: readline.get_endidx()]

            try:
                matches = complete(shell.completions(), line)
            finally:
                let_go()

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

            try:
                if not handle(shell, line):
                    break
            finally:
                let_go()
    finally:
        try:
            readline.write_history_file(history)
        except OSError:
            pass


def let_go() -> None:
    """
    Close each connection that isn't inside a transaction, where Django's
    rules for a connection's age would: with them as they are, every one.
    """
    for connection in connections.all(initialized_only=True):
        if not connection.in_atomic_block:
            connection.close_if_unusable_or_obsolete()

import re
from pathlib import Path

import psycopg
import pytest
from django.db import connection
from rich.console import Console
from typer.testing import CliRunner

from chatddx.core.utils import ensure_identity
from chatddx.manage import app
from chatddx.repl.cli import let_go
from chatddx.repl.commands import COMMANDS, Command, handle
from chatddx.repl.shell import Repl

pytestmark = pytest.mark.django_db


def test_the_repl_needs_an_identity():
    result = CliRunner().invoke(app, ["repl", "nobody"])

    assert result.exit_code == 1
    assert "no identity 'nobody'" in result.stderr


def test_a_session_can_be_piped_in(tmp_path: Path):

    result = CliRunner().invoke(
        app,
        ["repl", "alice", "--history", str(tmp_path / "history")],
        input="cell free-text qwen3-8b-awq@fake\nshow\nquit\n",
    )

    assert result.exit_code == 0, result.output
    # a seed drawn as it starts, in the prompt
    assert re.search(
        r"alice #\d{1,5}> cell free-text qwen3-8b-awq@fake\n", result.output
    )
    assert re.search(
        r"alice free-text×qwen3-8b-awq@fake #\d{1,5}> show\n", result.output
    )
    assert "the LLM's default, 'on'" in result.output


# a transactional test may find the session's seed flushed away: alice will do


@pytest.mark.django_db(transaction=True)
def test_an_idle_repl_holds_no_connection(tmp_path: Path):
    _ = ensure_identity("alice")
    assert connection.connection is not None

    result = CliRunner().invoke(
        app,
        ["repl", "alice", "--history", str(tmp_path / "history")],
        input="stacks\nquit\n",
    )

    assert result.exit_code == 0, result.output
    assert connection.connection is None


@pytest.mark.django_db(transaction=True)
def test_a_dropped_connection_is_said_and_the_next_line_opens_another():
    _ = ensure_identity("alice")
    repl = Repl("alice", Console(record=True, width=200), seed=None)
    assert handle(repl, "stacks")

    settings = connection.settings_dict
    backend = connection.connection.info.backend_pid
    with psycopg.connect(
        dbname=settings["NAME"], user=settings["USER"], host=settings["HOST"]
    ) as other:
        _ = other.execute("select pg_terminate_backend(%s)", [backend])

    assert handle(repl, "stacks")
    assert "the database failed: terminating connection" in repl.console.export_text()

    let_go()
    assert handle(repl, "cases")

    listed = repl.console.export_text()
    assert "the database failed" not in listed
    assert listed.endswith(" cases\n")


def test_ctrl_c_ends_the_command_not_the_repl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):

    def pressed(_repl: Repl) -> None:
        raise KeyboardInterrupt

    monkeypatch.setitem(COMMANDS, "cases", Command((), "", pressed))

    result = CliRunner().invoke(
        app,
        ["repl", "alice", "--history", str(tmp_path / "history")],
        input="cases\nstacks\nquit\n",
    )

    assert result.exit_code == 0, result.output
    assert re.search(r"> cases\n\n\(interrupted\)\nalice #\d+> stacks\n", result.output)
    assert "qwen3-8b-awq@fake" in result.output

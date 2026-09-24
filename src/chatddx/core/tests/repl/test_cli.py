"""`chatddx repl IDENTITY`, as the command line runs it."""

from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from chatddx.manage import app

pytestmark = pytest.mark.django_db


def test_the_repl_needs_an_identity():
    result = CliRunner().invoke(app, ["repl", "nobody"])

    assert result.exit_code == 1
    assert "no identity 'nobody'" in result.stderr


def test_a_session_can_be_piped_in(provision: Callable[..., None], tmp_path: Path):
    provision()

    result = CliRunner().invoke(
        app,
        ["repl", "alex", "--history", str(tmp_path / "history")],
        input="cell free-text qwen3-8b-awq@fake\nshow\nquit\n",
    )

    assert result.exit_code == 0, result.output
    assert "alex> cell free-text qwen3-8b-awq@fake\n" in result.output
    assert "alex free-text×qwen3-8b-awq@fake> show\n" in result.output
    assert "the model's default, 'on'" in result.output

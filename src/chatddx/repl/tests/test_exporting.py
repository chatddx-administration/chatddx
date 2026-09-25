"""`export` writes your runs of the cell as an inspect log."""

from collections.abc import Callable
from pathlib import Path

import pytest

type Say = Callable[..., str]

pytestmark = pytest.mark.django_db


def test_export_writes_your_runs_of_the_cell_where_you_say(say: Say, tmp_path: Path):
    written = say(
        "cell plan qwen3-8b-awq@fake",
        "run case-1",
        "run case-1 5",
        f"export {tmp_path}",
    )

    [path] = tmp_path.glob("*.eval")

    assert f"2 samples of 1 case, in up to 2 epochs: {path}" in written
    assert (
        "scored by reciprocal_rank, warning_mentions, disposition_mentions" in written
    )
    assert f"to see it: inspect view --log-dir {tmp_path}" in written


def test_export_needs_a_cell_and_your_runs_of_it(say: Say):
    assert "the cell needs a configuration and a stack" in say("export")
    assert "alex has no runs of the cell" in say(
        "cell plan qwen3-8b-awq@fake", "export"
    )
